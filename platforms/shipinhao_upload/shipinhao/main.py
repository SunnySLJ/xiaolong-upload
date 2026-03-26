# -*- coding: utf-8 -*-
"""
视频号助手上传 - 纯 CDP（nodriver）

视频号助手: https://channels.weixin.qq.com/platform
发表视频: https://channels.weixin.qq.com/platform/post/create
登录方式: 微信扫码
"""
from datetime import datetime
import os
import asyncio
import json

# 修复 nodriver Cookie.from_json 在新版 Chrome 中缺少 sameParty 的 KeyError
def _patch_nodriver_cookie():
    try:
        from nodriver.cdp import network
        _orig_from_json = network.Cookie.from_json
        @classmethod
        def _patched(cls, json_dict):
            d = dict(json_dict)
            if "sameParty" not in d:
                d["sameParty"] = False
            return _orig_from_json.__func__(cls, d)
        network.Cookie.from_json = _patched
    except Exception:
        pass
_patch_nodriver_cookie()

import nodriver as uc
from conf import LOCAL_CHROME_PATH, LOCAL_CHROME_HEADLESS, AUTH_MODE
from shipinhao.browser import get_browser, try_connect_existing_chrome
from common.utils import need_cookie_file, has_text_in_page as _has_text
from common.loggers import shipinhao_logger


# 视频号助手发表视频页面
SPH_UPLOAD_URL = "https://channels.weixin.qq.com/platform/post/create"
SPH_BASE_URL = "https://channels.weixin.qq.com"
# 视频号标题建议简短，描述可达1000字
SPH_TITLE_MAX = 64
SPH_TAGS_MAX = 10


def _js_find_file_input():
    """查找 file input：iframe 内 + shadow DOM"""
    return """
    (function(){
        function findIn(el){
            var inp = el.querySelector('input[type=file][accept*="video"]');
            if(inp) return inp;
            inp = el.querySelector('input[type=file]');
            return inp || null;
        }
        function search(doc, depth){
            if(!doc || depth>4) return null;
            var r = findIn(doc);
            if(r) return r;
            var ifs = doc.querySelectorAll('iframe');
            for(var i=0;i<ifs.length;i++){
                try{
                    if(ifs[i].contentDocument){
                        r = search(ifs[i].contentDocument, depth+1);
                        if(r) return r;
                    }
                }catch(e){}
            }
            var all = doc.querySelectorAll('*');
            for(var j=0;j<all.length;j++){
                if(all[j].shadowRoot){
                    r = search(all[j].shadowRoot, depth+1);
                    if(r) return r;
                }
            }
            return null;
        }
        return search(document, 0);
    })()
    """


async def _upload_file_via_cdp(tab, file_path: str) -> bool:
    """通过 CDP 设置文件，支持 iframe + shadow DOM 内的 input。直接用 object_id（request_node 对 iframe 内元素易失败）"""
    try:
        from nodriver import cdp
        abs_path = os.path.abspath(file_path)
        result = await tab.send(
            cdp.runtime.evaluate(
                expression=_js_find_file_input(),
                return_by_value=False,
            )
        )
        robj = result[0] if isinstance(result, (list, tuple)) else result
        err = result[1] if isinstance(result, (list, tuple)) and len(result) > 1 else None
        if err or not robj:
            return False
        oid = getattr(robj, "object_id", None)
        if not oid or (hasattr(robj, "type_") and getattr(robj, "subtype", None) == "null"):
            return False
        # 直接用 object_id，CDP 支持；request_node 对 iframe 内元素常返回 NodeId(0)
        await tab.send(cdp.dom.set_file_input_files(files=[abs_path], object_id=oid))
        return True
    except Exception as e:
        shipinhao_logger.info(f"[-] CDP 上传失败: {e}")
        return False


async def _upload_file_via_native_dialog(tab, file_path: str) -> bool:
    """点击上传后通过系统文件选择器填入路径（Mac: Cmd+Shift+G）"""
    try:
        import platform
        import pyautogui
        abs_path = os.path.abspath(file_path)
        # 点击上传按钮打开文件选择对话框
        btn = await tab.find("上传", best_match=True, timeout=2)
        if not btn:
            return False
        await btn.click()
        await tab.sleep(2)
        # 聚焦到文件对话框后，用键盘输入路径
        if platform.system() == "Darwin":
            pyautogui.hotkey("command", "shift", "g")
        else:
            pyautogui.hotkey("ctrl", "l")
        await asyncio.sleep(0.5)
        pyautogui.write(abs_path, interval=0.02)
        await asyncio.sleep(0.3)
        pyautogui.press("enter")
        await asyncio.sleep(0.5)
        pyautogui.press("enter")
        shipinhao_logger.info("[-] 已通过系统对话框填入路径")
        return True
    except Exception as e:
        shipinhao_logger.debug(f"native dialog: {e}")
        return False


async def _fill_text(el, text: str) -> bool:
    if not text:
        return True
    try:
        await el.click()
        await el.send_keys(text)
        return True
    except Exception:
        pass
    try:
        j = json.dumps(text, ensure_ascii=False)
        await el.apply(f"""(el) => {{
            el.focus();
            const t = {j};
            if (el.contentEditable === 'true') {{
                el.innerText = t;
                el.dispatchEvent(new InputEvent('input', {{bubbles: true}}));
            }} else {{
                el.value = t;
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
            }}
        }}""")
        return True
    except Exception as e:
        shipinhao_logger.debug(f"_fill_text 失败: {e}")
        return False


def _js_fill_title_desc(title: str, desc: str, tags: list) -> str:
    """在 iframe + shadow DOM 内查找并填充标题、文案。话题由 _try_fill_topics_via_click 用 insertText 追加。"""
    t = json.dumps(title[:SPH_TITLE_MAX], ensure_ascii=False)
    d = json.dumps(desc or "", ensure_ascii=False)
    return f"""
    (function() {{
        var foundTitle = null, foundDesc = null;
        function setVal(el, val) {{
            if (!el) return false;
            el.focus();
            if (el.contentEditable === 'true') {{
                el.innerText = val;
                el.dispatchEvent(new InputEvent('input', {{bubbles: true, data: val}}));
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
            }} else {{
                el.value = val;
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
            }}
            return true;
        }}
        function search(doc, depth) {{
            if (!doc || depth > 4) return;
            if (!foundTitle) {{
                var el = doc.querySelector('input[placeholder*="标题"]') || doc.querySelector('input[placeholder*="填写"]')
                    || doc.querySelector('.title-input') || doc.querySelector('input.weui-desktop-form__input');
                if (el) foundTitle = el;
            }}
            if (!foundDesc) {{
                var ed = doc.querySelector('.input-editor') || doc.querySelector('.ql-editor');
                if (ed) foundDesc = ed;
                else {{
                    var ce = doc.querySelectorAll('[contenteditable="true"]');
                    for (var i = 0; i < ce.length; i++) {{
                        if (ce[i].classList.contains('input-editor') || ce[i].classList.contains('ql-editor')) {{ foundDesc = ce[i]; break; }}
                    }}
                    if (!foundDesc && ce.length > 1) foundDesc = ce[1];
                    if (!foundDesc && ce.length) foundDesc = ce[0];
                }}
            }}
            if (foundTitle && foundDesc) return;
            doc.querySelectorAll('iframe').forEach(function(fr) {{
                try {{ if (fr.contentDocument) search(fr.contentDocument, depth + 1); }} catch(e) {{}}
            }});
            doc.querySelectorAll('*').forEach(function(el) {{
                if (el.shadowRoot) search(el.shadowRoot, depth + 1);
            }});
        }}
        search(document, 0);
        var ok = 0;
        if (foundTitle) {{ setVal(foundTitle, {t}); ok++; }}
        if (foundDesc) {{ setVal(foundDesc, {d}); ok++; }}
        return ok;
    }})()
    """


async def _try_fill_topics_via_click(tab, tags: list) -> bool:
    """点击 #话题 按钮并输入每个话题（视频号需在文案框输入 #话题名 才能成为可点击话题）"""
    if not tags:
        return True
    try:
        js = """
        (function(tags) {
            var found = null;
            function search(doc, depth) {
                if (!doc || depth > 4) return;
                var ed = doc.querySelector('.input-editor');
                if (ed) { found = ed; return; }
                doc.querySelectorAll('iframe').forEach(function(fr) {
                    try { if (fr.contentDocument) search(fr.contentDocument, depth + 1); } catch(e) {}
                });
                doc.querySelectorAll('*').forEach(function(el) {
                    if (el.shadowRoot) search(el.shadowRoot, depth + 1);
                });
            }
            search(document, 0);
            if (!found) return false;
            found.focus();
            var sel = window.getSelection();
            sel.selectAllChildren(found);
            sel.collapseToEnd();
            var toAdd = tags.map(function(t) { return '#' + t; }).join(' ');
            document.execCommand('insertText', false, ' ' + toAdd);
            return true;
        })(%s)
        """ % json.dumps(tags, ensure_ascii=False)
        ok = await tab.evaluate(js, return_by_value=True)
        if ok:
            shipinhao_logger.info(f"[-] 已追加话题: {', '.join(tags)}")
            return True
    except Exception as e:
        shipinhao_logger.debug(f"追加话题失败: {e}")
    return False


def _gen_title_desc_from_path(file_path: str, tags: list = None) -> tuple:
    from common.utils import gen_title_desc_from_path
    return gen_title_desc_from_path(file_path, title_max=SPH_TITLE_MAX, style="rich", tags=tags)


async def _check_logged_in(browser, account_file: str, account_name: str) -> tuple[bool, object]:
    """返回 (是否已登录, tab)。登录成功时 tab 已在发表页"""
    if need_cookie_file(AUTH_MODE) and os.path.exists(account_file):
        try:
            await browser.cookies.load(account_file)
        except Exception:
            pass

    tab = await browser.get(SPH_UPLOAD_URL)
    await tab.sleep(2)

    # 视频号登录页检测：微信扫码
    url_lower = (tab.url or "").lower()
    if "login" in url_lower or "mp.weixin.qq.com" in url_lower:
        shipinhao_logger.info("[+] 检测到登录页，cookie/会话已失效")
        return False, None
    if await _has_text(tab, "微信扫码") or await _has_text(tab, "扫码登录") or await _has_text(tab, "请使用微信扫码"):
        shipinhao_logger.info("[+] 检测到登录页，需要微信扫码登录")
        await _send_wechat_login_notice()
        return False, None

    shipinhao_logger.info("[+] 已登录")
    return True, tab


async def cookie_auth(account_file: str, account_name: str = "default") -> tuple[bool, object, object]:
    """返回 (是否已登录, browser, tab) 或 (False, None, None)。登录成功时返回可复用的 browser/tab"""
    for try_reuse in (True, False):
        res = await get_browser(
            headless=LOCAL_CHROME_HEADLESS, account_name=account_name, try_reuse=try_reuse
        )
        browser, was_reused = res if isinstance(res, tuple) else (res, False)
        try:
            ok, tab = await _check_logged_in(browser, account_file, account_name)
            if ok and tab is not None:
                return True, browser, tab
        except (StopIteration, RuntimeError) as e:
            if try_reuse:
                shipinhao_logger.warning(f"[-] 复用 Chrome 失败 ({e})，改用新浏览器")
                continue
            raise
        if not was_reused:
            browser.stop()
    return False, None, None


async def shipinhao_setup(account_file: str, handle: bool = False, account_name: str = "default"):
    # cookie 模式：不调用 try_connect，避免误关 Connect 脚本启动的 Chrome
    if not need_cookie_file(AUTH_MODE):
        existing = await try_connect_existing_chrome()
        if existing:
            shipinhao_logger.info("[+] 已连接并复用已有浏览器")
            return True, existing

    if need_cookie_file(AUTH_MODE) and not os.path.exists(account_file):
        if not handle:
            shipinhao_logger.info("[+] cookie 文件不存在，请先登录（handle=True）")
            return False, None
    else:
        ok, browser, tab = await cookie_auth(account_file, account_name)
        if ok and browser is not None and tab is not None:
            return True, (browser, tab)

    if not handle:
        return False, None

    shipinhao_logger.info("[+] 需要登录，即将打开浏览器...")
    browser, tab = await shipinhao_cookie_gen(account_file, account_name)
    return True, (browser, tab)


async def _is_login_page(tab) -> bool:
    url = (tab.url or "").lower()
    # 已进入平台/post/create 等则非登录页
    if "platform" in url and "post" in url:
        return False
    if "channels.weixin.qq.com" in url and "login" not in url and "mp.weixin" not in url:
        return False
    if "login" in url or "mp.weixin" in url:
        return True
    if await _has_text(tab, "微信扫码", timeout=1):
        return True
    if await _has_text(tab, "扫码登录", timeout=1):
        return True
    if await _has_text(tab, "请使用微信扫码", timeout=1):
        return True
    return False


async def shipinhao_cookie_gen(account_file: str, account_name: str = "default"):
    was_reused = False
    for try_reuse in (True, False):
        res = await get_browser(headless=False, account_name=account_name, try_reuse=try_reuse)
        browser, was_reused = res if isinstance(res, tuple) else (res, False)
        try:
            tab = await browser.get(SPH_BASE_URL)
            break
        except (StopIteration, RuntimeError) as e:
            if try_reuse:
                shipinhao_logger.warning(f"[-] 复用 Chrome 失败 ({e})，改用新浏览器")
            else:
                raise
    await tab.sleep(2)
    if AUTH_MODE == "connect":
        shipinhao_logger.info("[+] 已连接你的 Chrome，请在浏览器中用微信扫码登录视频号助手")
    else:
        shipinhao_logger.info("[+] 请用微信扫码登录视频号助手，登录成功约 15 秒内会自动跳转")

    poll_interval = 15
    max_wait = 600
    for elapsed in range(0, max_wait, poll_interval):
        await tab.sleep(poll_interval)
        tab = await browser.get(SPH_UPLOAD_URL)
        await tab.sleep(2)
        if not await _is_login_page(tab):
            shipinhao_logger.info("[+] 检测到已登录，正在保存...")
            break
        shipinhao_logger.info(f"[-] 等待登录中... ({elapsed + poll_interval}s)")
    else:
        shipinhao_logger.error("[-] 登录超时")
        if not was_reused:
            browser.stop()
        raise TimeoutError("登录超时，请重试")

    if need_cookie_file(AUTH_MODE):
        try:
            cookie_dir = os.path.dirname(account_file)
            os.makedirs(cookie_dir, exist_ok=True)
            shipinhao_logger.info(f"[-] 保存 cookie...")
            await asyncio.wait_for(browser.cookies.save(account_file), timeout=5.0)
            shipinhao_logger.info("[+] 登录信息已保存")
        except (asyncio.TimeoutError, Exception) as e:
            shipinhao_logger.warning(f"[-] 保存 cookie 跳过: {e}")

    shipinhao_logger.info("[+] 已在发表页，准备进入上传流程")
    return browser, tab


class ShipinhaoVideo(object):
    def __init__(
        self,
        title: str,
        file_path: str,
        tags: list,
        publish_date: datetime,
        account_file: str,
        thumbnail_path=None,
        description: str = "",
        account_name: str = "default",
    ):
        _title = (title or "").strip()
        _desc = (description or "").strip()
        if not _title or not _desc:
            def_title, def_desc = _gen_title_desc_from_path(file_path)
            _title = _title or def_title
            _desc = _desc or def_desc
        self.title = _title[:SPH_TITLE_MAX]
        self.file_path = file_path
        self.tags = (tags or [])[:SPH_TAGS_MAX]
        self.description = _desc
        self.publish_date = publish_date
        self.account_file = account_file
        self.account_name = account_name
        self.date_format = "%Y年%m月%d日 %H:%M"
        self.local_executable_path = LOCAL_CHROME_PATH
        self.headless = LOCAL_CHROME_HEADLESS
        self.thumbnail_path = thumbnail_path

    async def upload(self, existing_browser=None, existing_tab=None) -> None:
        reuse = existing_browser is not None and existing_tab is not None
        keep_browser_open = reuse
        if reuse:
            browser, tab = existing_browser, existing_tab
        else:
            for try_reuse in (True, False):
                res = await get_browser(
                    headless=self.headless, account_name=self.account_name, try_reuse=try_reuse
                )
                browser, was_reused = res if isinstance(res, tuple) else (res, False)
                keep_browser_open = was_reused
                if need_cookie_file(AUTH_MODE) and os.path.exists(self.account_file):
                    try:
                        await browser.cookies.load(self.account_file)
                    except Exception:
                        pass
                try:
                    tab = await browser.get(SPH_UPLOAD_URL)
                    break
                except (StopIteration, RuntimeError) as e:
                    if try_reuse:
                        shipinhao_logger.warning(f"[-] 复用 Chrome 失败 ({e})，改用新浏览器")
                    else:
                        raise
        try:
            shipinhao_logger.info(f"[+] 正在上传 - {os.path.basename(self.file_path)}")
            shipinhao_logger.info("[-] Step 0: 打开发表页...")
            await tab.sleep(3)

            ok_step1 = await _upload_file_via_cdp(tab, self.file_path)
            if not ok_step1:
                shipinhao_logger.info("[-] 尝试系统文件选择器...")
                ok_step1 = await _upload_file_via_native_dialog(tab, self.file_path)
            if ok_step1:
                shipinhao_logger.info("[-] Step 1 完成: 已设置文件")

            if not ok_step1:
                if not reuse:
                    if await _is_login_page(tab):
                        shipinhao_logger.error("[+] 未进入发表页，请检查网络或登录状态")
                        return
                    if await _has_text(tab, "微信扫码") or await _has_text(tab, "扫码登录"):
                        shipinhao_logger.error("[+] 未登录，请先运行并用微信扫码登录")
                        return

                async def _do_step1():
                    shipinhao_logger.info("[-] Step 1: 查找上传 input（含 iframe）...")
                    if await _upload_file_via_cdp(tab, self.file_path):
                        shipinhao_logger.info("[-] Step 1 完成: CDP 已设置文件")
                        return True
                    upload_inp = None
                    _t = 3
                    for sel in ('input[type="file"][accept*="video"]', 'input[type="file"][accept*="*"]', 'input[type="file"]'):
                        try:
                            all_inps = await tab.select_all(sel, timeout=_t, include_frames=True)
                            if all_inps:
                                upload_inp = all_inps[0]
                                shipinhao_logger.info(f"[-] 找到 {sel}")
                                break
                        except Exception as e:
                            shipinhao_logger.debug(f"select_all {sel}: {e}")
                            continue
                    if not upload_inp:
                        for sel in ("div[class*='upload'] input", "input.upload-input", ".upload-area input"):
                            try:
                                all_inps = await tab.select_all(sel, timeout=_t, include_frames=True)
                                if all_inps:
                                    upload_inp = all_inps[0]
                                    shipinhao_logger.info(f"[-] 找到: {sel}")
                                    break
                            except Exception:
                                continue
                    if not upload_inp:
                        for btn_text in ("上传视频", "选择视频", "点击上传", "上传", "添加视频", "选择文件"):
                            try:
                                btn = await tab.find(btn_text, best_match=True, timeout=2)
                                if btn:
                                    shipinhao_logger.info(f"[-] 点击按钮: {btn_text}")
                                    await btn.click()
                                    await tab.sleep(3)
                                    all_inps = await tab.select_all('input[type="file"]', timeout=_t, include_frames=True)
                                    if all_inps:
                                        upload_inp = all_inps[0]
                                        break
                            except Exception:
                                continue
                    if upload_inp:
                        try:
                            await upload_inp.send_file(self.file_path)
                            shipinhao_logger.info("[-] Step 1 完成: 已发送文件")
                            return True
                        except Exception as e:
                            shipinhao_logger.warning(f"[-] send_file 失败: {e}，尝试 CDP fallback")
                    if await _upload_file_via_cdp(tab, self.file_path):
                        shipinhao_logger.info("[-] Step 1 完成: CDP 已设置文件")
                        return True
                    return False

                try:
                    ok = await asyncio.wait_for(_do_step1(), timeout=45.0)
                except asyncio.TimeoutError:
                    shipinhao_logger.error("[-] Step 1 超时（45s）")
                    ok = False
                if not ok:
                    shipinhao_logger.error("[-] Step 1 失败: 未找到上传 input，请检查页面结构")
                    return

            async def _upload_done():
                for txt in ("上传成功", "上传完成", "100%", "处理中", "转码"):
                    if await _has_text(tab, txt, timeout=0.6):
                        return True
                try:
                    for sel in ("input[placeholder*='标题']", ".title-input", ".weui-desktop-form__input"):
                        el = await tab.select(sel, timeout=0.4)
                        if el:
                            return True
                except Exception:
                    pass
                return False

            for i in range(240):
                await tab.sleep(0.5)
                if await _upload_done():
                    shipinhao_logger.success("[-] 视频上传完毕")
                    break
                if i > 0 and i % 6 == 0:
                    shipinhao_logger.info(f"[-] 上传中... ({i // 2}s)")
            else:
                shipinhao_logger.warning("[-] Step 2: 超时，尝试继续填写标题...")
            shipinhao_logger.info("[-] Step 2 完成")

            await tab.sleep(0.5)

            shipinhao_logger.info("[-] 正在填充标题、文案和话题...")
            try:
                filled = await tab.evaluate(
                    _js_fill_title_desc(self.title, self.description, self.tags),
                    return_by_value=True,
                )
                if filled and int(filled) >= 1:
                    shipinhao_logger.info(f"[-] Step 3+4 完成: 标题和文案已填充")
                    if self.tags:
                        await asyncio.sleep(0.3)
                        await _try_fill_topics_via_click(tab, self.tags)
                        shipinhao_logger.info(f"[-] 已添加 {len(self.tags)} 个话题")
                else:
                    shipinhao_logger.warning("[-] JS 填充未命中，尝试 nodriver 选择器...")
                    raise ValueError("js fill failed")
            except Exception:
                desc_text = self.description
                if self.tags:
                    desc_text += (" " if desc_text else "") + " " + " ".join(f"#{t}" for t in self.tags)
                for sel in ("input[placeholder*='标题']", "input[placeholder*='填写']", ".title-input"):
                    try:
                        el = await tab.select(sel, timeout=1)
                        if el:
                            await _fill_text(el, self.title[:SPH_TITLE_MAX])
                            break
                    except Exception:
                        continue
                for sel in (".input-editor", ".ql-editor", "[contenteditable='true']"):
                    try:
                        els = await tab.select_all(sel, timeout=1, include_frames=True)
                        if els and desc_text:
                            await _fill_text(els[0], desc_text)
                            break
                    except Exception:
                        continue

            try:
                for label in ("原创声明", "同意", "遵守", "协议"):
                    chk = await tab.find(label, best_match=True, timeout=1)
                    if chk:
                        await chk.click()
                        await tab.sleep(0.3)
                        break
            except Exception:
                pass

            shipinhao_logger.info("[-] Step 5: 点击发表...")

            async def _scroll_bottom():
                try:
                    await tab.evaluate("""
                        window.scrollTo(0, 9e9);
                        document.documentElement.scrollTop = 9e9;
                        document.querySelectorAll('[class*="content"], [class*="layout"], [class*="form"]').forEach(function(el) {
                            if (el.scrollHeight > el.clientHeight) el.scrollTop = el.scrollHeight;
                        });
                    """)
                    await tab.sleep(0.4)
                except Exception:
                    pass

            async def _do_click(el) -> bool:
                try:
                    await el.apply("(el) => { el.scrollIntoView({block: 'center'}); el.focus(); }")
                    await tab.sleep(0.3)
                    await el.click()
                    return True
                except Exception:
                    try:
                        await el.apply("(el) => { el.scrollIntoView({block: 'center'}); el.dispatchEvent(new MouseEvent('click', {bubbles: true})); }")
                        return True
                    except Exception:
                        return False

            clicked = False
            for _ in range(3):
                await _scroll_bottom()
            try:
                await tab.evaluate("""
                    document.querySelectorAll('[class*="tip"],[class*="banner"],[class*="notification"]').forEach(function(el) {
                        if (el.style) el.style.pointerEvents = 'none';
                    });
                """)
                await tab.sleep(0.2)
            except Exception:
                pass

            for retry in range(3):
                for btn_text in ("发表", "发布", "视频发表", "立即发表", "发布视频"):
                    try:
                        btn = await tab.find(btn_text, best_match=True, timeout=2)
                        if btn:
                            disabled = await btn.apply("(el) => !!el.disabled")
                            if disabled and retry < 2:
                                shipinhao_logger.info("[-] 发表按钮禁用中，等待表单校验...")
                                await tab.sleep(1.5)
                                await _scroll_bottom()
                                break
                            if await _do_click(btn):
                                shipinhao_logger.info(f"[-] Step 5 完成: 已点击「{btn_text}」")
                                clicked = True
                                break
                    except Exception:
                        continue
                if clicked:
                    break
                if retry < 2:
                    await tab.sleep(0.8)
                    await _scroll_bottom()

            if not clicked:
                for sel in ("button.weui-desktop-btn_primary", "button[type='submit']", ".weui-desktop-btn_primary", "[class*='publish'] button", "[class*='submit']"):
                    try:
                        btn = await tab.select(sel, timeout=1)
                        if btn:
                            txt = await btn.apply("(el) => (el.innerText || '').trim()")
                            if "发表" in str(txt) or "发布" in str(txt):
                                if await _do_click(btn):
                                    shipinhao_logger.info("[-] Step 5 完成: 已点击发表(选择器)")
                                    clicked = True
                                    break
                    except Exception:
                        continue

            if not clicked:
                try:
                    ok = await tab.evaluate("""
                        (function() {
                            var btns = document.querySelectorAll('button, [class*="btn"], a[class*="btn"]');
                            for (var i = 0; i < btns.length; i++) {
                                var b = btns[i];
                                var t = (b.innerText || '').trim();
                                if ((t === '发表' || t === '发布' || t.indexOf('发表') >= 0) && b.offsetParent && !b.closest('[class*="aside"]')) {
                                    b.scrollIntoView({block: 'center'});
                                    b.style.pointerEvents = 'auto';
                                    if (b.disabled) b.removeAttribute('disabled');
                                    b.click();
                                    return true;
                                }
                            }
                            return false;
                        })()
                    """, return_by_value=True)
                    if ok:
                        shipinhao_logger.info("[-] Step 5 完成: JS 已点击发表")
                        clicked = True
                except Exception as e:
                    shipinhao_logger.debug(f"[-] JS 点击失败: {e}")

            if not clicked:
                shipinhao_logger.error("[-] Step 5 失败: 未找到或无法点击发表按钮")
                return

            await tab.sleep(1)

            for i in range(24):
                await tab.sleep(0.5)
                url = (tab.url or "").lower()
                if "success" in url or "list" in url or "content" in url:
                    shipinhao_logger.success("[-] 视频发表成功")
                    break
                if await _has_text(tab, "发表成功", timeout=1) or await _has_text(tab, "发布成功", timeout=1):
                    shipinhao_logger.success("[-] 视频发表成功")
                    break
                if i > 0 and i % 4 == 0:
                    shipinhao_logger.info(f"[-] 等待发表结果... ({i // 2}s)")
            else:
                shipinhao_logger.info("[-] 发表已提交，即将退出")

            if need_cookie_file(AUTH_MODE):
                try:
                    await asyncio.wait_for(browser.cookies.save(self.account_file), timeout=5.0)
                    shipinhao_logger.success("[-] cookie 更新完毕")
                except (asyncio.TimeoutError, Exception) as e:
                    shipinhao_logger.warning(f"[-] 保存 cookie 跳过: {e}")
            await tab.sleep(1)
            if keep_browser_open:
                try:
                    uc.util.get_registered_instances().discard(browser)
                except Exception:
                    pass
        finally:
            if not keep_browser_open:
                browser.stop()

    async def main(self):
        await self.upload()
