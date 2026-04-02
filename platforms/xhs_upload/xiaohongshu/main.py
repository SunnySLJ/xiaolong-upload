# -*- coding: utf-8 -*-
"""
小红书创作者平台上传 - 纯 CDP（nodriver）
"""
from datetime import datetime
import os
import asyncio
import json
import urllib.parse
import urllib.request

from conf import LOCAL_CHROME_PATH, LOCAL_CHROME_HEADLESS, AUTH_MODE, CDP_DEBUG_PORT
from xiaohongshu.browser import get_browser
from common.utils import need_cookie_file
from common.loggers import xiaohongshu_logger


XHS_UPLOAD_URL = "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video"
XHS_TITLE_MAX = 20
XHS_TAGS_MAX = 5


def _open_target_tab(url: str, port: int = CDP_DEBUG_PORT) -> bool:
    encoded = urllib.parse.quote(url, safe=":/?&=%")
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/json/new?{encoded}",
            method="PUT",
            headers={"User-Agent": "xiaohongshu-upload"},
        )
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def _find_existing_publish_tab(browser, url_hint: str = XHS_UPLOAD_URL):
    hint = (url_hint or "").lower()
    try:
        tabs = getattr(browser, "tabs", None) or []
        for tab in tabs:
            try:
                url = (getattr(tab, "url", None) or getattr(getattr(tab, "target", None), "url", None) or "").lower()
                if "creator.xiaohongshu.com" in url and "publish" in url:
                    return tab
                if hint and url == hint:
                    return tab
            except Exception:
                continue
    except Exception:
        pass
    return None


async def _browser_get_with_retry(browser, url: str, *, retries: int = 2, wait_seconds: float = 1.5):
    last_error = None
    existing = _find_existing_publish_tab(browser, url)
    if existing is not None:
        return existing
    for attempt in range(retries + 1):
        try:
            return await browser.get(url)
        except (StopIteration, RuntimeError) as e:
            last_error = e
            if "StopIteration" not in str(e) and "coroutine raised StopIteration" not in str(e):
                raise
            _open_target_tab(url)
            await asyncio.sleep(wait_seconds)
    raise RuntimeError(f"browser.get failed after retry: {last_error}")


def _js_find_file_input():
    """查找 file input：支持 iframe + shadow DOM（与视频号逻辑一致）"""
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
    """通过 CDP 设置文件，支持 iframe + shadow DOM，使用 object_id"""
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
        await tab.send(cdp.dom.set_file_input_files(files=[abs_path], object_id=oid))
        return True
    except Exception as e:
        xiaohongshu_logger.debug(f"CDP 上传 fallback 失败: {e}")
        return False


async def _upload_file_via_native_dialog(tab, file_path: str) -> bool:
    """点击上传后通过系统文件选择器填入路径（Mac: Cmd+Shift+G）"""
    try:
        import platform
        import pyautogui
        abs_path = os.path.abspath(file_path)
        for btn_text in ("上传视频", "选择视频", "点击上传", "上传"):
            try:
                btn = await tab.find(btn_text, best_match=True, timeout=1)
                if btn:
                    await btn.click()
                    await tab.sleep(2)
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
                    xiaohongshu_logger.info("[-] 已通过系统对话框填入路径")
                    return True
            except Exception:
                continue
        return False
    except Exception as e:
        xiaohongshu_logger.debug(f"native dialog: {e}")
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
        xiaohongshu_logger.debug(f"_fill_text 失败: {e}")
        return False


from common.utils import has_text_in_page as _has_text


def _gen_title_desc_from_path(file_path: str) -> tuple:
    from common.utils import gen_title_desc_from_path
    return gen_title_desc_from_path(file_path, title_max=20, style="simple")


async def _check_logged_in(browser, account_file: str, account_name: str) -> tuple[bool, object]:
    """返回 (是否已登录, tab)。登录成功时 tab 已在发布页"""
    if need_cookie_file(AUTH_MODE) and os.path.exists(account_file):
        try:
            await browser.cookies.load(account_file)
        except Exception:
            pass

    tab = await _browser_get_with_retry(browser, XHS_UPLOAD_URL)
    await tab.sleep(2)

    if "login" in (tab.url or "") or "creator.xiaohongshu.com/login" in (tab.url or ""):
        xiaohongshu_logger.info("[+] 检测到登录页，cookie/会话已失效")
        return False, None
    if await _has_text(tab, "短信登录") or await _has_text(tab, "发送验证码") or await _has_text(tab, "扫码登录"):
        xiaohongshu_logger.info("[+] 检测到登录页，需要登录")
        return False, None

    xiaohongshu_logger.info("[+] 已登录")
    return True, tab


async def cookie_auth(account_file: str, account_name: str = "default") -> tuple[bool, object, object]:
    """返回 (是否已登录, browser, tab)。登录成功时返回可复用的 browser/tab"""
    for try_reuse in (True, False):
        try:
            res = await get_browser(headless=LOCAL_CHROME_HEADLESS, account_name=account_name, try_reuse=try_reuse)
        except Exception as e:
            if try_reuse:
                xiaohongshu_logger.warning(f"[-] 连接浏览器失败 ({e})，改用下一种方式")
                continue
            xiaohongshu_logger.warning(f"[-] 连接浏览器失败 ({e})")
            return False, None, None
        browser, was_reused = res if isinstance(res, tuple) else (res, False)
        try:
            ok, tab = await _check_logged_in(browser, account_file, account_name)
            if ok and tab is not None:
                return True, browser, tab
        except (StopIteration, RuntimeError) as e:
            if try_reuse:
                xiaohongshu_logger.warning(f"[-] 复用 Chrome 失败 ({e})，改用新浏览器")
                continue
            raise
        if not was_reused:
            try:
                browser.stop()
            except Exception:
                pass
    return False, None, None


async def xiaohongshu_setup(account_file: str, handle: bool = False, account_name: str = "default"):
    if need_cookie_file(AUTH_MODE) and not os.path.exists(account_file):
        if not handle:
            xiaohongshu_logger.info("[+] cookie 文件不存在，请先登录（handle=True）")
            return False, None
    else:
        ok, browser, tab = await cookie_auth(account_file, account_name)
        if ok and browser is not None and tab is not None:
            return True, (browser, tab, False)  # cookie_auth 开的浏览器，上传后可关闭

    if not handle:
        return False, None

    xiaohongshu_logger.info("[+] 需要登录，即将打开浏览器...")
    browser, tab, keep_open = await xiaohongshu_cookie_gen(account_file, account_name)
    return True, (browser, tab, keep_open)


async def _is_login_page(tab) -> bool:
    url = (tab.url or "").lower()
    if "publish" in url or "creator/home" in url or "note-manager" in url or "content/upload" in url:
        return False
    if "login" in url:
        return True
    if await _has_text(tab, "短信登录", timeout=1):
        return True
    if await _has_text(tab, "验证码登录", timeout=1):
        return True
    if await _has_text(tab, "APP扫一扫登录", timeout=1):
        return True
    if await _has_text(tab, "发送验证码", timeout=1):
        return True
    if await _has_text(tab, "扫码登录", timeout=1):
        return True
    return False


async def xiaohongshu_cookie_gen(account_file: str, account_name: str = "default"):
    was_reused = False
    for try_reuse in (True, False):
        res = await get_browser(headless=False, account_name=account_name, try_reuse=try_reuse)
        browser, was_reused = res if isinstance(res, tuple) else (res, False)
        try:
            tab = await _browser_get_with_retry(browser, "https://creator.xiaohongshu.com/")
            break
        except (StopIteration, RuntimeError) as e:
            if try_reuse:
                xiaohongshu_logger.warning(f"[-] 复用 Chrome 失败 ({e})，改用新浏览器")
            else:
                raise
    await tab.sleep(2)
    if AUTH_MODE == "connect":
        xiaohongshu_logger.info("[+] 已连接你的 Chrome，请在浏览器中登录小红书创作者中心")
    else:
        xiaohongshu_logger.info("[+] 请在浏览器中扫码或验证码登录小红书，登录成功约 15 秒内会自动跳转")

    poll_interval = 3
    max_wait = 600
    for elapsed in range(0, max_wait, poll_interval):
        await tab.sleep(poll_interval)
        tab = await _browser_get_with_retry(browser, XHS_UPLOAD_URL)
        await tab.sleep(2)
        if not await _is_login_page(tab):
            xiaohongshu_logger.info("[+] 检测到已登录，正在保存...")
            break
        xiaohongshu_logger.info(f"[-] 等待登录中... ({elapsed + poll_interval}s)")
    else:
        xiaohongshu_logger.error("[-] 登录超时")
        if not was_reused:
            browser.stop()
        raise TimeoutError("登录超时，请重试")

    if need_cookie_file(AUTH_MODE):
        try:
            cookie_dir = os.path.dirname(account_file)
            os.makedirs(cookie_dir, exist_ok=True)
            xiaohongshu_logger.info(f"[-] 保存 cookie...")
            await asyncio.wait_for(browser.cookies.save(account_file), timeout=5.0)
            xiaohongshu_logger.info("[+] 登录信息已保存")
        except (asyncio.TimeoutError, Exception) as e:
            xiaohongshu_logger.warning(f"[-] 保存 cookie 跳过: {e}")

    xiaohongshu_logger.info("[+] 已在发布页，准备进入上传流程")
    if was_reused:
        xiaohongshu_logger.info("[+] 复用已打开的 Chrome，完成后不关闭")
    return browser, tab, was_reused


class XiaohongshuVideo(object):
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
        self.title = _title[:XHS_TITLE_MAX]
        self.file_path = file_path
        self.tags = (tags or [])[:XHS_TAGS_MAX]
        self.description = _desc
        self.publish_date = publish_date
        self.account_file = account_file
        self.account_name = account_name
        self.date_format = "%Y年%m月%d日 %H:%M"
        self.local_executable_path = LOCAL_CHROME_PATH
        self.headless = LOCAL_CHROME_HEADLESS
        self.thumbnail_path = thumbnail_path

    async def upload(self, existing_browser=None, existing_tab=None, keep_browser_open: bool = False) -> bool:
        reuse = existing_browser is not None and existing_tab is not None
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
                    tab = await _browser_get_with_retry(browser, XHS_UPLOAD_URL)
                    break
                except (StopIteration, RuntimeError) as e:
                    if try_reuse:
                        xiaohongshu_logger.warning(f"[-] 复用 Chrome 失败 ({e})，改用新浏览器")
                    else:
                        raise
        try:
            xiaohongshu_logger.info(f"[+] 正在上传 - {os.path.basename(self.file_path)}")
            xiaohongshu_logger.info("[-] Step 0: 打开发布页...")
            await tab.sleep(5)

            if not reuse:
                if "login" in (tab.url or ""):
                    xiaohongshu_logger.error("[+] 未进入发布页，请检查网络或登录状态")
                    return False
                if await _has_text(tab, "短信登录") or await _has_text(tab, "发送验证码"):
                    xiaohongshu_logger.error("[+] 未登录，请先运行并完成扫码/验证码登录")
                    return False

            async def _do_step1():
                xiaohongshu_logger.info("[-] Step 1: 查找上传 input...")
                # 1) 先尝试点击「选择视频/上传视频」露出上传区域（页面可能默认在图文）
                for btn_text in ("选择视频", "上传视频", "点击上传"):
                    try:
                        btn = await tab.find(btn_text, best_match=True, timeout=1.5)
                        if btn:
                            xiaohongshu_logger.info(f"[-] 点击「{btn_text}」...")
                            await btn.click()
                            await tab.sleep(2)
                            break
                    except Exception:
                        continue

                upload_inp = None
                _t = 2
                for sel in ('input[type="file"][accept*="video"]', 'input[type="file"]'):
                    try:
                        all_inps = await tab.select_all(sel, timeout=_t, include_frames=True)
                        if all_inps:
                            upload_inp = all_inps[0]
                            xiaohongshu_logger.info(f"[-] 找到 {sel}")
                            break
                    except Exception:
                        continue
                if not upload_inp:
                    for sel in ("div[class^='upload-content'] input.upload-input", "input.upload-input"):
                        try:
                            upload_inp = await tab.select(sel, timeout=_t)
                            if upload_inp:
                                xiaohongshu_logger.info(f"[-] 找到: {sel}")
                                break
                        except Exception:
                            continue
                if upload_inp:
                    try:
                        await upload_inp.send_file(self.file_path)
                        xiaohongshu_logger.info("[-] Step 1 完成: 已发送文件")
                        return True
                    except Exception as e:
                        xiaohongshu_logger.warning(f"[-] send_file 失败: {e}，尝试 CDP fallback")

                if await _upload_file_via_cdp(tab, self.file_path):
                    xiaohongshu_logger.info("[-] Step 1 完成: CDP 已设置文件")
                    return True

                if await _upload_file_via_native_dialog(tab, self.file_path):
                    return True

                return False

            try:
                ok = await asyncio.wait_for(_do_step1(), timeout=30.0)
            except asyncio.TimeoutError:
                xiaohongshu_logger.error("[-] Step 1 超时（30s），请手动上传或检查页面")
                return False
            if not ok:
                xiaohongshu_logger.error("[-] Step 1 失败: 未找到上传 input，请检查页面结构")
                return False

            async def _upload_done():
                for txt in ("上传成功", "上传完成", "100%"):
                    if await _has_text(tab, txt, timeout=0.8):
                        return True
                try:
                    el = await tab.select("div.plugin.title-container input.d-text, .notranslate", timeout=0.5)
                    if el:
                        return True
                except Exception:
                    pass
                return False

            for i in range(180):
                await tab.sleep(0.5)
                if await _upload_done():
                    xiaohongshu_logger.success("[-] 视频上传完毕")
                    break
                if i % 4 == 0 and i > 0:
                    xiaohongshu_logger.info(f"[-] 上传中... ({i // 2}s)")
            else:
                xiaohongshu_logger.warning("[-] Step 2: 超时，尝试继续填写标题...")
            xiaohongshu_logger.info("[-] Step 2 完成")

            await tab.sleep(1)

            xiaohongshu_logger.info("[-] 正在填充标题...")
            title_el = None
            for sel in (
                "div.plugin.title-container input.d-text",
                ".notranslate",
                "input[placeholder*='标题']",
                "input[placeholder*='填写标题']",
            ):
                try:
                    title_el = await tab.select(sel, timeout=2)
                    if title_el:
                        xiaohongshu_logger.info(f"[-] 标题框: {sel}")
                        break
                except Exception:
                    continue
            if title_el:
                await _fill_text(title_el, self.title[:20])
                xiaohongshu_logger.info("[-] Step 3 完成: 标题已填充")
            else:
                xiaohongshu_logger.warning("[-] Step 3: 未找到标题框，跳过")

            xiaohongshu_logger.info("[-] 正在填充描述和话题...")
            desc_text = self.description
            if self.tags:
                desc_text += (" " if desc_text else "") + " ".join(f"#{t}" for t in self.tags)
            desc_el = None
            for sel in (".ql-editor", ".ProseMirror", ".tiptap", "div[data-placeholder*='描述']"):
                try:
                    els = await tab.select_all(sel, timeout=2)
                    if els:
                        desc_el = els[0]
                        xiaohongshu_logger.info(f"[-] 文案框: {sel}")
                        break
                except Exception:
                    continue
            if not desc_el:
                try:
                    els = await tab.select_all("[contenteditable='true']", timeout=2)
                    if len(els) > 1:
                        desc_el = els[1]
                    elif els:
                        desc_el = els[0]
                    if desc_el:
                        xiaohongshu_logger.info("[-] 文案框: contenteditable")
                except Exception:
                    pass
            if desc_el and desc_text:
                await _fill_text(desc_el, desc_text)
                xiaohongshu_logger.info(f"[-] Step 4 完成: 文案+话题已填充，共 {len(self.tags)} 个")
            elif desc_text:
                xiaohongshu_logger.warning("[-] Step 4: 未找到文案框，跳过")

            try:
                for label in ("社区公约", "遵守", "同意"):
                    chk = await tab.find(label, best_match=True, timeout=1)
                    if chk:
                        await chk.click()
                        await tab.sleep(0.3)
                        break
            except Exception:
                pass

            xiaohongshu_logger.info("[-] Step 5: 点击发布...")
            pub_btn = await tab.find("发布", best_match=True, timeout=5)
            if pub_btn:
                await pub_btn.click()
                xiaohongshu_logger.info("[-] Step 5 完成: 已点击发布")
            else:
                xiaohongshu_logger.error("[-] Step 5 失败: 未找到发布按钮")
                return False

            await tab.sleep(2)

            publish_confirmed = False
            for _ in range(60):
                await tab.sleep(0.5)
                url = (tab.url or "").lower()
                if "publish/success" in url or "note-manager" in url or "manage" in url:
                    xiaohongshu_logger.success("[-] 视频发布成功")
                    publish_confirmed = True
                    break
                if await _has_text(tab, "发布成功", timeout=1):
                    xiaohongshu_logger.success("[-] 视频发布成功")
                    publish_confirmed = True
                    break
                xiaohongshu_logger.info("[-] 视频正在发布中...")
            else:
                xiaohongshu_logger.error("[-] Step 6 失败: 发布流程已触发，但未确认成功")
                return False

            if need_cookie_file(AUTH_MODE):
                try:
                    await asyncio.wait_for(browser.cookies.save(self.account_file), timeout=5.0)
                    xiaohongshu_logger.success("[-] cookie 更新完毕")
                except (asyncio.TimeoutError, Exception) as e:
                    xiaohongshu_logger.warning(f"[-] 保存 cookie 跳过: {e}")
            await tab.sleep(1)
            return publish_confirmed
        finally:
            if not keep_browser_open:
                browser.stop()

    async def main(self):
        await self.upload()
