# -*- coding: utf-8 -*-
"""
快手创作者平台上传 - 纯 CDP（nodriver）
"""
from datetime import datetime
import os
import asyncio
import json
import sys
import time

import nodriver as uc
from conf import LOCAL_CHROME_PATH, LOCAL_CHROME_HEADLESS, AUTH_MODE
from kuaishou.browser import get_browser
from common.utils import need_cookie_file, has_text_in_page as _has_text
from common.loggers import kuaishou_logger


KS_UPLOAD_URL = "https://cp.kuaishou.com/article/publish/video"
KS_HOME_URL = "https://cp.kuaishou.com/"
KS_TITLE_MAX = 15
KS_TAGS_MAX = 4


def _step_log(msg: str, elapsed: float | None = None):
    """带时间戳的步骤日志，elapsed 为秒数时追加耗时"""
    ts = datetime.now().strftime("%H:%M:%S")
    out = f"[{ts}] {msg}"
    if elapsed is not None and elapsed >= 0:
        out += f" (耗时 {elapsed:.1f}s)"
    kuaishou_logger.info(out)
    sys.stdout.flush()
    sys.stderr.flush()


async def _upload_file_via_cdp(tab, file_path: str) -> bool:
    """通过 CDP 设置文件，支持 iframe + shadow DOM，使用 object_id。"""
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
            return await _upload_file_via_cdp_legacy(tab, file_path)
        oid = getattr(robj, "object_id", None)
        if not oid or (hasattr(robj, "type_") and getattr(robj, "subtype", None) == "null"):
            return await _upload_file_via_cdp_legacy(tab, file_path)
        await tab.send(cdp.dom.set_file_input_files(files=[abs_path], object_id=oid))
        return True
    except Exception as e:
        kuaishou_logger.debug(f"CDP 上传 fallback 失败: {e}")
        return await _upload_file_via_cdp_legacy(tab, file_path)


def _js_find_file_input() -> str:
    return r"""
    (() => {
        function findIn(doc){
            if(!doc || !doc.querySelectorAll) return null;
            const sels = [
                'input[type="file"][accept*="video"]',
                'input[type="file"][accept*="mp4"]',
                'input[type="file"]',
                'input.upload-input',
                '[class*="upload"] input[type="file"]',
                '[class*="Upload"] input',
                '[data-testid*="upload"] input',
                'input[accept*="video"]',
            ];
            for (const sel of sels) {
                const inp = doc.querySelector(sel);
                if (inp) return inp;
            }
            return null;
        }
        function search(doc, depth){
            if(!doc || depth > 4) return null;
            let r = findIn(doc);
            if(r) return r;
            const ifs = doc.querySelectorAll ? doc.querySelectorAll('iframe') : [];
            for(let i = 0; i < ifs.length; i++){
                try{
                    if(ifs[i].contentDocument){
                        r = search(ifs[i].contentDocument, depth + 1);
                        if(r) return r;
                    }
                }catch(e){}
            }
            const all = doc.querySelectorAll ? doc.querySelectorAll('*') : [];
            for(let j = 0; j < all.length; j++){
                if(all[j].shadowRoot){
                    r = search(all[j].shadowRoot, depth + 1);
                    if(r) return r;
                }
            }
            return null;
        }
        return search(document, 0);
    })()
    """


async def _upload_file_via_cdp_legacy(tab, file_path: str) -> bool:
    try:
        from nodriver import cdp
        doc = await tab.send(cdp.dom.get_document(-1, True))
        if not doc or not getattr(doc, "node_id", None):
            return False
        for sel in ('input[type="file"][accept*="video"]', 'input[type="file"]'):
            node_id = await tab.send(cdp.dom.query_selector(doc.node_id, sel))
            if node_id and (not hasattr(node_id, "to_json") or node_id.to_json() != 0):
                await tab.send(cdp.dom.set_file_input_files(files=[os.path.abspath(file_path)], node_id=node_id))
                return True
        return False
    except Exception as e:
        kuaishou_logger.debug(f"CDP 上传 fallback 失败: {e}")
        return False


async def _fill_text(el, text: str) -> bool:
    if not text:
        return True
    # 含 # 时优先用 JS 设置，避免 send_keys 对 # 的特殊处理
    j = json.dumps(text, ensure_ascii=False)
    try:
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
        kuaishou_logger.debug(f"_fill_text JS 失败: {e}")
    try:
        await el.click()
        await el.send_keys(text)
        return True
    except Exception as e:
        kuaishou_logger.debug(f"_fill_text send_keys 失败: {e}")
    return False


async def _try_select_first(tab, selectors: tuple, timeout: float = 0.6, use_select_all: bool = False):
    """尝试多个选择器，返回第一个匹配元素"""
    for sel in selectors:
        try:
            if use_select_all:
                els = await tab.select_all(sel, timeout=timeout)
                if els:
                    return els[0]
            else:
                el = await tab.select(sel, timeout=timeout)
                if el:
                    return el
        except Exception:
            continue
    return None


def _gen_title_desc_from_path(file_path: str) -> tuple:
    from common.utils import gen_title_desc_from_path
    return gen_title_desc_from_path(file_path, title_max=KS_TITLE_MAX, style="simple")


async def _check_logged_in(browser, account_file: str, account_name: str) -> tuple[bool, object, object]:
    """返回 (是否已登录, browser, tab)，登录成功时 tab 已在发布页"""
    if need_cookie_file(AUTH_MODE) and os.path.exists(account_file):
        try:
            await browser.cookies.load(account_file)
        except Exception:
            pass

    # 若已有标签页在发布页，直接复用，避免刷新（connect/profile 均适用）
    tab = None
    try:
        tabs = getattr(browser, "tabs", None)
        if tabs:
            for t in tabs:
                try:
                    url = (getattr(t, "url", None) or getattr(getattr(t, "target", None), "url", None) or "").lower()
                    if "cp.kuaishou.com" in url and "article/publish" in url:
                        tab = t
                        _step_log("复用已打开的发布页，无需刷新")
                        break
                except Exception:
                    continue
    except Exception:
        pass

    if tab is None:
        _step_log("打开发布页...")
        tab = await browser.get(KS_UPLOAD_URL)
        await tab.sleep(2)

    for retry in range(3):
        url_lower = (tab.url or "").lower()
        if "login" in url_lower or "passport" in url_lower:
            kuaishou_logger.info("[+] 检测到登录页，cookie/会话已失效")
            return False, None, None
        if await _has_text(tab, "扫码登录") or await _has_text(tab, "短信登录") or await _has_text(tab, "发送验证码"):
            kuaishou_logger.info("[+] 检测到登录页，需要登录")
            return False, None, None
        if await _is_publish_ready(tab):
            kuaishou_logger.info("[+] 已登录，发布页已就绪")
            return True, browser, tab
        if retry < 2:
            kuaishou_logger.info("[-] 当前页面未识别到发布控件，等待页面继续加载...")
            await tab.sleep(2)

    try:
        diag = await tab.evaluate(
            """
            JSON.stringify({
              url: location.href,
              title: document.title || '',
              buttons: Array.from(document.querySelectorAll('button, [role="button"]'))
                .map((el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim())
                .filter(Boolean)
                .slice(0, 12)
            })
            """,
            return_by_value=True,
        )
        kuaishou_logger.warning(f"[-] 登录态诊断: {diag}")
    except Exception as e:
        kuaishou_logger.debug(f"[-] 登录态诊断失败: {e}")

    kuaishou_logger.info("[+] 当前页面不像登录页，但发布页未就绪，按未登录处理")
    return False, None, None


async def cookie_auth(account_file: str, account_name: str = "default") -> tuple[bool, object, object]:
    """返回 (是否已登录, browser, tab)，登录成功时返回可复用的 browser/tab"""
    _step_log("连接浏览器...")
    for try_reuse in (True, False):
        res = await get_browser(
            headless=LOCAL_CHROME_HEADLESS, account_name=account_name, try_reuse=try_reuse
        )
        browser, was_reused = res if isinstance(res, tuple) else (res, False)
        try:
            ok, ret_browser, tab = await _check_logged_in(browser, account_file, account_name)
            if ok and ret_browser is not None:
                return True, ret_browser, tab
        except (StopIteration, RuntimeError) as e:
            if try_reuse:
                kuaishou_logger.warning(f"[-] 复用 Chrome 失败 ({e})，改用新浏览器")
                continue
            raise
        if not was_reused:
            browser.stop()
    return False, None, None


async def kuaishou_setup(account_file: str, handle: bool = False, account_name: str = "default"):
    if need_cookie_file(AUTH_MODE) and not os.path.exists(account_file):
        if not handle:
            kuaishou_logger.info("[+] cookie 文件不存在，请先登录（handle=True）")
            return False, None
        kuaishou_logger.info("[+] 需要登录，即将打开浏览器...")
        browser, tab = await kuaishou_cookie_gen(account_file, account_name)
        return True, (browser, tab)
    ok, browser, tab = await cookie_auth(account_file, account_name)
    if ok:
        return True, (browser, tab)
    if not handle:
        return False, None
    kuaishou_logger.info("[+] 需要登录，即将打开浏览器...")
    browser, tab = await kuaishou_cookie_gen(account_file, account_name)
    return True, (browser, tab)


async def _is_login_page(tab) -> bool:
    url = (tab.url or "").lower()
    if await _is_publish_ready(tab):
        return False
    if "login" in url or "passport" in url:
        return True
    if await _has_text(tab, "登录", timeout=1):
        return True
    if await _has_text(tab, "扫码登录", timeout=1):
        return True
    if await _has_text(tab, "短信登录", timeout=1):
        return True
    if await _has_text(tab, "验证码", timeout=1):
        return True
    if await _has_text(tab, "手机号登录", timeout=1):
        return True
    return False


async def _is_publish_ready(tab) -> bool:
    """判断是否真正进入了可用的发布页，而不是仅仅不在登录页。"""
    selectors = (
        'input[type="file"][accept*="video"]',
        'input[type="file"][accept*="mp4"]',
        'input[type="file"]',
        'input.upload-input',
        '[class*="upload"] input[type="file"]',
        '[class*="Upload"] input',
        '[data-testid*="upload"] input',
        'input[accept*="video"]',
    )

    for sel in selectors:
        try:
            els = await tab.select_all(sel, timeout=0.6, include_frames=True)
            if els:
                return True
        except Exception:
            continue

    for text in ("上传视频", "选择视频", "点击上传", "拖拽上传", "发布作品", "发布"):
        try:
            if await _has_text(tab, text, timeout=0.6):
                return True
        except Exception:
            continue

    try:
        payload = await tab.evaluate(
            """
            (() => {
              const text = (document.body && document.body.innerText || '').slice(0, 12000);
              const title = document.title || '';
              const buttons = Array.from(document.querySelectorAll('button, [role="button"], a, span, div'))
                .map((el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim())
                .filter(Boolean)
                .slice(0, 60);
              const hasUploadInput = !!document.querySelector(
                'input[type="file"], input[accept*="video"], input[accept*="mp4"], [class*="upload"] input[type="file"]'
              );
              const hasLoginText = /扫码登录|验证码登录|短信登录|登录快手创作者服务平台|手机号登录|账号登录|请完成验证后继续访问|同意并登录|快手APP扫码/.test(text + '\\n' + title);
              const hasReadyUi = hasUploadInput ||
                /发布作品|发布视频|上传视频|上传图文|上传全景视频|拖拽视频到此或点击上传|作品描述|封面设置|定时发布/.test(text) ||
                buttons.some((v) => /发布作品|发布视频|上传视频|选择视频|点击上传|发布/.test(v));
              return hasReadyUi && !hasLoginText;
            })()
            """,
            return_by_value=True,
        )
        if payload:
            return True
    except Exception:
        pass

    return False


async def kuaishou_cookie_gen(account_file: str, account_name: str = "default"):
    for try_reuse in (True, False):
        res = await get_browser(headless=False, account_name=account_name, try_reuse=try_reuse)
        browser, was_reused = res if isinstance(res, tuple) else (res, False)
        try:
            tab = await browser.get(KS_HOME_URL)
            break
        except (StopIteration, RuntimeError) as e:
            if try_reuse:
                kuaishou_logger.warning(f"[-] 复用 Chrome 失败 ({e})，改用新浏览器")
            else:
                raise
    await tab.sleep(2)
    if AUTH_MODE == "connect":
        kuaishou_logger.info("[+] 已连接你的 Chrome，请在浏览器中登录快手创作者中心")
    else:
        kuaishou_logger.info("[+] 请在浏览器中扫码或验证码登录快手，登录成功约 15 秒内会自动跳转")

    poll_interval = 3
    max_wait = 600
    for elapsed in range(0, max_wait, poll_interval):
        await tab.sleep(poll_interval)
        tab = await browser.get(KS_UPLOAD_URL)
        await tab.sleep(2)
        if not await _is_login_page(tab):
            kuaishou_logger.info("[+] 检测到已登录，正在保存...")
            break
        kuaishou_logger.info(f"[-] 等待登录中... ({elapsed + poll_interval}s)")
    else:
        kuaishou_logger.error("[-] 登录超时")
        if not was_reused:
            browser.stop()
        raise TimeoutError("登录超时，请重试")

    if need_cookie_file(AUTH_MODE):
        try:
            cookie_dir = os.path.dirname(account_file)
            os.makedirs(cookie_dir, exist_ok=True)
            kuaishou_logger.info("[-] 保存 cookie...")
            await asyncio.wait_for(browser.cookies.save(account_file), timeout=5.0)
            kuaishou_logger.info("[+] 登录信息已保存")
        except (asyncio.TimeoutError, Exception) as e:
            kuaishou_logger.warning(f"[-] 保存 cookie 跳过: {e}")

    kuaishou_logger.info("[+] 已在发布页，准备进入上传流程")
    return browser, tab


class KuaishouVideo(object):
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
        self.title = _title[:KS_TITLE_MAX]
        self.file_path = file_path
        self.tags = [str(t).replace("#", "").strip() for t in (tags or []) if t][:KS_TAGS_MAX]  # 存纯文本，展示时加 #
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
        if reuse:
            browser, tab = existing_browser, existing_tab
        else:
            for try_reuse in (True, False):
                res = await get_browser(
                    headless=self.headless, account_name=self.account_name, try_reuse=try_reuse
                )
                browser, _ = res if isinstance(res, tuple) else (res, False)
                if need_cookie_file(AUTH_MODE) and os.path.exists(self.account_file):
                    try:
                        await browser.cookies.load(self.account_file)
                    except Exception:
                        pass
                try:
                    tab = await browser.get(KS_UPLOAD_URL)
                    break
                except (StopIteration, RuntimeError) as e:
                    if try_reuse:
                        kuaishou_logger.warning(f"[-] 复用 Chrome 失败 ({e})，改用新浏览器")
                    else:
                        raise
        try:
            _step_log(f"正在上传 - {os.path.basename(self.file_path)}")
            t0_step0 = time.perf_counter()
            _step_log("Step 0: 打开发布页...")
            await tab.sleep(1.5)
            _step_log("Step 0 完成", elapsed=time.perf_counter() - t0_step0)

            if not reuse:
                url_lower = (tab.url or "").lower()
                if "login" in url_lower or "passport" in url_lower:
                    kuaishou_logger.error("[+] 未进入发布页，请检查网络或登录状态")
                    return
                if await _has_text(tab, "登录") or await _has_text(tab, "扫码"):
                    kuaishou_logger.error("[+] 未登录，请先运行并完成扫码/验证码登录")
                    return

            UPLOAD_SELECTORS = (
                'input[type="file"][accept*="video"]',
                'input[type="file"][accept*="mp4"]',
                'input[type="file"]',
                'input.upload-input',
                '[class*="upload"] input[type="file"]',
                '[class*="Upload"] input',
                '[data-testid*="upload"] input',
                'input[accept*="video"]',
            )

            async def _do_step1():
                t0 = time.perf_counter()
                _step_log("Step 1: 查找上传 input...")
                upload_inp = None
                _t = 1.2
                for sel in UPLOAD_SELECTORS:
                    try:
                        all_inps = await tab.select_all(sel, timeout=_t, include_frames=True)
                        if all_inps:
                            upload_inp = all_inps[0]
                            _step_log(f"找到上传 input: {str(sel)[:50]}")
                            break
                    except Exception:
                        continue
                if not upload_inp:
                    try:
                        for btn_text in ("上传视频", "选择视频", "点击上传", "拖拽上传", "上传"):
                            btn = await tab.find(btn_text, best_match=True, timeout=_t)
                            if btn:
                                await btn.click()
                                await tab.sleep(1)
                                upload_inp = await _try_select_first(tab, ('input[type="file"]',), _t)
                                if upload_inp:
                                    break
                    except Exception:
                        pass
                if upload_inp:
                    try:
                        await upload_inp.send_file(self.file_path)
                        _step_log("Step 1 完成: 已发送文件", elapsed=time.perf_counter() - t0)
                        return True
                    except Exception as e:
                        kuaishou_logger.warning(f"[-] send_file 失败: {e}，尝试 CDP fallback")
                if await _upload_file_via_cdp(tab, self.file_path):
                    _step_log("Step 1 完成: CDP 已设置文件", elapsed=time.perf_counter() - t0)
                    return True
                return False

            try:
                ok = await asyncio.wait_for(_do_step1(), timeout=25.0)
            except asyncio.TimeoutError:
                kuaishou_logger.error("[-] Step 1 超时（25s），请手动上传或检查页面")
                return
            if not ok:
                kuaishou_logger.error("[-] Step 1 失败: 未找到上传 input，请检查页面结构")
                return

            UPLOAD_DONE_SELECTORS = (
                "input[placeholder*='标题']", "input[placeholder*='填写']",
                "div[placeholder*='作品描述']", "[placeholder*='作品描述']",
                "textarea[placeholder*='描述']", ".title-input", "input.d-text",
                ".ql-editor", ".ProseMirror", ".notranslate", "[contenteditable='true']",
            )

            async def _upload_done():
                for txt in ("上传成功", "上传完成", "100%"):
                    if await _has_text(tab, txt, timeout=0.5):
                        return True
                el = await _try_select_first(tab, UPLOAD_DONE_SELECTORS, 0.3)
                return el is not None

            t0_step2 = time.perf_counter()
            _step_log("Step 2: 等待视频上传...")
            for i in range(180):
                await tab.sleep(0.4)
                if await _upload_done():
                    _step_log("Step 2 完成: 视频上传完毕", elapsed=time.perf_counter() - t0_step2)
                    break
                if i % 5 == 0 and i > 0:
                    _step_log(f"上传中... {i * 0.4:.0f}s")
            else:
                _step_log("Step 2: 超时，尝试继续填写标题...", elapsed=time.perf_counter() - t0_step2)
                kuaishou_logger.warning("[-] Step 2: 超时，尝试继续填写标题...")

            await tab.sleep(0.5)

            # 关闭弹窗：仅点击 modal 内的关闭按钮
            t0 = time.perf_counter()
            _step_log("关闭弹窗...")
            for _ in range(3):
                clicked = False
                try:
                    for sel in (
                        ".ant-modal-wrap .ant-modal-close",
                        ".ant-modal .ant-modal-close",
                        "[class*='modal'] [class*='close']",
                    ):
                        try:
                            els = await tab.select_all(sel, timeout=0.3)
                            if els:
                                await els[0].click()
                                _step_log("已关闭弹窗")
                                clicked = True
                                break
                        except Exception:
                            continue
                    if not clicked:
                        for txt in ("关闭", "跳过", "知道了"):
                            try:
                                btn = await tab.find(txt, best_match=True, timeout=0.3)
                                if btn:
                                    await btn.click()
                                    _step_log(f"已点击: {txt}")
                                    clicked = True
                                    break
                            except Exception:
                                continue
                except Exception:
                    pass
                if not clicked:
                    break
                await tab.sleep(0.2)
            _step_log("关闭弹窗完成", elapsed=time.perf_counter() - t0)

            TITLE_SELECTORS = (
                "input[placeholder*='标题']", "input[placeholder*='填写标题']",
                "input[placeholder*='添加标题']", "[placeholder*='标题']",
                ".title-input", "input.d-text", ".notranslate",
                "[class*='title'] input", "input[type='text'][placeholder]",
                "input[placeholder]", "input[type='text']",
            )
            t0 = time.perf_counter()
            _step_log("Step 3: 正在填充标题...")
            title_el = await _try_select_first(tab, TITLE_SELECTORS, 0.35)
            if title_el:
                kuaishou_logger.info("[-] 找到标题框")
                await _fill_text(title_el, self.title[:KS_TITLE_MAX])
                _step_log("Step 3 完成: 标题已填充", elapsed=time.perf_counter() - t0)
            else:
                _step_log("Step 3: 未找到标题框，跳过", elapsed=time.perf_counter() - t0)

            DESC_SELECTORS = (
                "div[placeholder*='作品描述']", "[placeholder*='作品描述']",
                "textarea[placeholder*='作品描述']", "textarea[placeholder*='智能文案']",
                "[placeholder*='智能文案']", "[data-placeholder*='描述']",
                ".ql-editor", ".ProseMirror", ".tiptap", "[class*='editor']",
                "textarea[placeholder*='描述']", "[class*='desc']", "[class*='Desc']",
                "div[contenteditable='true']", "[contenteditable='true']",
            )
            t0_step4 = time.perf_counter()
            _step_log("Step 4: 正在填充描述和话题...")
            # 文案不含 #，标签必须带 #，最多 4 个
            desc_text = str(self.description or "").replace("#", "").strip()
            tags_raw = [str(t).replace("#", "").strip() for t in self.tags[:KS_TAGS_MAX] if t]
            tags_with_hash = ["#" + t for t in tags_raw if t]  # 每个标签前加 #
            if tags_with_hash:
                desc_text += (" " if desc_text else "") + " " + " ".join(tags_with_hash)
            desc_el = await _try_select_first(tab, DESC_SELECTORS, 0.4, use_select_all=True)
            if not desc_el:
                try:
                    els = await tab.select_all("[contenteditable='true']", timeout=0.5)
                    if len(els) > 1:
                        desc_el = els[1]
                    elif els:
                        desc_el = els[0]
                    if desc_el:
                        kuaishou_logger.info("[-] 文案框: contenteditable")
                except Exception:
                    pass
            if desc_el:
                kuaishou_logger.info("[-] 找到文案框")
            if desc_el and desc_text:
                await _fill_text(desc_el, desc_text)
                _step_log(f"Step 4 完成: 文案+话题已填充，共 {len(self.tags)} 个", elapsed=time.perf_counter() - t0_step4)
            elif desc_text:
                _step_log("Step 4: 未找到文案框，跳过", elapsed=time.perf_counter() - t0_step4)
                kuaishou_logger.warning("[-] Step 4: 未找到文案框，跳过")

            try:
                for label in ("社区公约", "遵守", "同意", "协议"):
                    chk = await tab.find(label, best_match=True, timeout=0.5)
                    if chk:
                        await chk.click()
                        await tab.sleep(0.15)
                        break
            except Exception:
                pass

            await tab.sleep(1.0)

            t0_step5 = time.perf_counter()
            _step_log("Step 5: 点击发布...")

            async def _scroll_bottom():
                try:
                    await tab.evaluate("""
                        window.scrollTo(0, 9e9);
                        document.documentElement.scrollTop = 9e9;
                        document.querySelectorAll('[class*="content"], [class*="layout"], .ant-layout-content').forEach(function(el) {
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
                for btn_text in ("发布", "确认发布", "立即发布"):
                    try:
                        btn = await tab.find(btn_text, best_match=True, timeout=1.5)
                        if btn:
                            disabled = await btn.apply("(el) => !!el.disabled")
                            if disabled and retry < 2:
                                _step_log("发布按钮禁用中，等待表单校验...")
                                await tab.sleep(1.5)
                                await _scroll_bottom()
                                break
                            if await _do_click(btn):
                                _step_log(f"Step 5 完成: 已点击「{btn_text}」", elapsed=time.perf_counter() - t0_step5)
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
                for sel in ("button.ant-btn-primary", ".ant-btn-primary", "button[type='submit']"):
                    try:
                        btn = await tab.select(sel, timeout=0.8)
                        if btn:
                            txt = await btn.apply("(el) => (el.innerText || '').trim()")
                            if "发布" in str(txt):
                                if await _do_click(btn):
                                    _step_log("Step 5 完成: 已点击发布(选择器)", elapsed=time.perf_counter() - t0_step5)
                                    clicked = True
                                    break
                    except Exception:
                        continue

            if not clicked:
                try:
                    ok = await tab.evaluate("""
                        (function() {
                            var btns = document.querySelectorAll('button, [class*="btn"]');
                            for (var i = 0; i < btns.length; i++) {
                                var b = btns[i];
                                var t = (b.innerText || '').trim();
                                if (t === '发布' && b.offsetParent && !b.closest('[class*="aside"]') && !b.closest('[class*="menu"]')) {
                                    b.scrollIntoView({block: 'center'});
                                    b.style.pointerEvents = 'auto';
                                    if (b.disabled) b.removeAttribute('disabled');
                                    b.click();
                                    return true;
                                }
                            }
                            var cancel = null;
                            for (var j = 0; j < btns.length; j++) {
                                if ((btns[j].innerText || '').trim() === '取消') {
                                    cancel = btns[j];
                                    break;
                                }
                            }
                            if (cancel && cancel.previousElementSibling) {
                                var prev = cancel.previousElementSibling;
                                if (/发布/.test(prev.innerText || '')) {
                                    prev.scrollIntoView({block: 'center'});
                                    if (prev.disabled) prev.removeAttribute('disabled');
                                    prev.click();
                                    return true;
                                }
                            }
                            return false;
                        })()
                    """, return_by_value=True)
                    if ok:
                        _step_log("Step 5 完成: JS 已点击发布", elapsed=time.perf_counter() - t0_step5)
                        clicked = True
                except Exception as e:
                    kuaishou_logger.debug(f"[-] JS 点击失败: {e}")

            if not clicked:
                _step_log("Step 5 失败: 未找到或无法点击发布按钮", elapsed=time.perf_counter() - t0_step5)
                try:
                    diag = await tab.evaluate(
                        "JSON.stringify([].slice.call(document.querySelectorAll('button')).map(function(b){return b.innerText||'';}).slice(0,12))",
                        return_by_value=True,
                    )
                    kuaishou_logger.warning(f"[-] 页面按钮文案: {diag}")
                except Exception:
                    pass
                kuaishou_logger.error("[-] Step 5 失败: 未找到或无法点击发布按钮")
                return

            await tab.sleep(1)

            _step_log("Step 5b: 检查确认发布弹窗...")
            for _ in range(3):
                try:
                    confirm_btn = await tab.find("确认发布", best_match=True, timeout=0.8)
                    if confirm_btn:
                        await confirm_btn.click()
                        _step_log("已点击确认发布")
                        await tab.sleep(0.5)
                        break
                except Exception:
                    pass
                await tab.sleep(0.3)

            _step_log("Step 6: 等待发布完成...")
            publish_confirmed = False
            for idx in range(60):
                await tab.sleep(0.4)
                url = (tab.url or "").lower()
                if "success" in url or "manage" in url or "article" in url and "publish" not in url:
                    _step_log("视频发布成功")
                    publish_confirmed = True
                    break
                if await _has_text(tab, "发布成功", timeout=1):
                    _step_log("视频发布成功")
                    publish_confirmed = True
                    break
                if idx > 0 and idx % 5 == 0:
                    _step_log(f"发布中... {idx * 0.4:.0f}s")
            else:
                kuaishou_logger.error("[-] Step 6 失败: 发布流程已触发，但未确认成功")
                return False

            if need_cookie_file(AUTH_MODE):
                try:
                    await asyncio.wait_for(browser.cookies.save(self.account_file), timeout=5.0)
                    kuaishou_logger.success("[-] cookie 更新完毕")
                except (asyncio.TimeoutError, Exception) as e:
                    kuaishou_logger.warning(f"[-] 保存 cookie 跳过: {e}")
            await tab.sleep(0.5)
            # 从 nodriver 注册表移除，避免 atexit 时关闭浏览器
            try:
                uc.util.get_registered_instances().discard(browser)
            except Exception:
                pass
            return publish_confirmed
        finally:
            pass  # 不关闭浏览器，脚本结束后用户可继续操作

    async def main(self):
        await self.upload()
