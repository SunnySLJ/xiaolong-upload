# -*- coding: utf-8 -*-
"""
抖音创作者平台上传 - 纯 CDP（nodriver）

登录授权模式（conf.AUTH_MODE）：
  cookie  - 从 cookie 文件加载登录态，无登录流程；支持 Connect 脚本 + CDP 连接
  connect - 连接已有 Chrome
  profile - 固定用户目录，登录态保存
"""
from datetime import datetime
import os
import asyncio
import urllib.parse
import urllib.request

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

from conf import LOCAL_CHROME_PATH, LOCAL_CHROME_HEADLESS, AUTH_MODE, CDP_DEBUG_PORT
from douyin.browser import (
    DOUYIN_UPLOAD_URL,
    get_browser,
    try_connect_existing_chrome,
    ensure_connect_login_chrome,
    attach_login_chrome,
)
from common.utils import need_cookie_file, load_cookies_from_file, save_cookies_to_json
from common.loggers import douyin_logger

try:
    from nodriver.core import util as _nodriver_util
except ImportError:
    _nodriver_util = None

from common.utils import has_text_in_page as _has_text


def _open_target_tab(url: str, port: int = CDP_DEBUG_PORT) -> bool:
    encoded = urllib.parse.quote(url, safe=":/?&=%")
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/json/new?{encoded}",
            method="PUT",
            headers={"User-Agent": "douyin-upload"},
        )
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def _find_existing_upload_tab(browser, url_hint: str = DOUYIN_UPLOAD_URL):
    hint = (url_hint or "").lower()
    try:
        tabs = getattr(browser, "tabs", None) or []
        for tab in tabs:
            try:
                url = (getattr(tab, "url", None) or getattr(getattr(tab, "target", None), "url", None) or "").lower()
                if "creator.douyin.com" in url and "content/upload" in url:
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
    existing = _find_existing_upload_tab(browser, url)
    if existing is not None:
        return existing
    for _ in range(retries + 1):
        try:
            return await browser.get(url)
        except (StopIteration, RuntimeError) as e:
            last_error = e
            if "StopIteration" not in str(e) and "coroutine raised StopIteration" not in str(e):
                raise
            _open_target_tab(url)
            await asyncio.sleep(wait_seconds)
    raise RuntimeError(f"browser.get failed after retry: {last_error}")


async def _check_logged_in(browser, account_file: str, account_name: str) -> bool:
    if need_cookie_file(AUTH_MODE) and os.path.exists(account_file):
        try:
            await load_cookies_from_file(browser, account_file)
        except Exception:
            pass

    tab = await _browser_get_with_retry(browser, DOUYIN_UPLOAD_URL)
    await tab.sleep(2)

    if "creator.douyin.com/creator-micro/content/upload" not in (tab.url or ""):
        douyin_logger.info("[+] 未进入上传页，可能需重新登录")
        return False

    if await _has_text(tab, "手机号登录") or await _has_text(tab, "扫码登录"):
        douyin_logger.info("[+] 检测到登录页，cookie 已失效，请用 save_douyin_cookie.py 更新 cookie")
        return False

    douyin_logger.info("[+] 已登录")
    return True


async def _wait_for_login(browser, account_file: str, account_name: str, timeout: int = 300, poll_interval: int = 5) -> bool:
    """等待用户在已打开的抖音登录页完成扫码登录。"""
    elapsed = 0
    while elapsed < timeout:
        if await _check_logged_in(browser, account_file, account_name):
            if need_cookie_file(AUTH_MODE):
                try:
                    ok = await asyncio.wait_for(save_cookies_to_json(browser, account_file), timeout=5.0)
                    if ok:
                        douyin_logger.success("[-] 登录后 cookie 已更新")
                except (asyncio.TimeoutError, Exception) as e:
                    douyin_logger.warning(f"[-] 登录后保存 cookie 跳过: {e}")
            return True
        douyin_logger.info(f"[-] 等待抖音扫码登录中... ({elapsed + poll_interval}s)")
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    douyin_logger.error("[-] 抖音登录超时")
    return False


async def _click_publish_button(tab) -> bool:
    """只点击真正的发布按钮，避免误点“高清发布”等其他入口。"""
    try:
        clicked = await tab.evaluate(
            """
            (() => {
              const nodes = Array.from(document.querySelectorAll('button, div[role="button"], span[role="button"]'));
              const target = nodes.find((el) => {
                const text = (el.innerText || el.textContent || '').trim();
                return text === '发布' || text === '立即发布';
              });
              if (!target) return false;
              target.click();
              return true;
            })()
            """,
            return_by_value=True,
        )
        if clicked:
            return True
    except Exception:
        pass
    try:
        btn = await tab.find("立即发布", best_match=True, timeout=1)
        if btn:
            await btn.click()
            return True
    except Exception:
        pass
    try:
        btn = await tab.find("发布", best_match=False, timeout=1)
        if btn:
            await btn.click()
            return True
    except Exception:
        pass
    return False


async def cookie_auth(account_file: str, account_name: str = "default", reuse_browser: bool = False):
    for try_reuse in (True, False):
        res = await get_browser(headless=LOCAL_CHROME_HEADLESS, account_name=account_name, try_reuse=try_reuse)
        browser, was_reused = res if isinstance(res, tuple) else (res, False)
        try:
            ok = await _check_logged_in(browser, account_file, account_name)
            if ok and reuse_browser:
                return (True, browser)
            if ok:
                return (True, None)
        except (StopIteration, RuntimeError) as e:
            if try_reuse:
                douyin_logger.warning(f"[-] 复用 Chrome 失败 ({e})，改用新浏览器")
                continue
            raise
        if not was_reused:
            browser.stop()
    return (False, None)


async def douyin_setup(account_file: str, handle: bool = False, account_name: str = "default"):
    existing = await try_connect_existing_chrome()
    if existing:
        douyin_logger.info("[+] 已连接并复用已有浏览器")
        return (True, existing)

    if ensure_connect_login_chrome():
        try:
            browser, tab = await attach_login_chrome()
            ok = await _check_logged_in(browser, account_file, account_name)
            if ok:
                douyin_logger.info("[+] 已连接抖音专用 connect Chrome")
                return (True, (browser, tab))
            if handle:
                douyin_logger.info("[+] 需要登录，请在抖音专用 connect Chrome 中完成扫码")
                if await _wait_for_login(browser, account_file, account_name):
                    checked_tab = await _browser_get_with_retry(browser, DOUYIN_UPLOAD_URL)
                    return (True, (browser, checked_tab))
                return (False, None)
        except Exception as e:
            douyin_logger.warning(f"[-] connect Chrome 预检失败 ({e})，继续尝试其他登录方式")

    if need_cookie_file(AUTH_MODE) and not os.path.exists(account_file):
        if handle:
            browser, tab = await attach_login_chrome()
            douyin_logger.info("[+] cookie 文件不存在，已打开抖音登录页，请完成扫码登录")
            if await _wait_for_login(browser, account_file, account_name):
                checked_tab = await _browser_get_with_retry(browser, DOUYIN_UPLOAD_URL)
                return (True, (browser, checked_tab))
            return (False, None)
        douyin_logger.info("[+] cookie 文件不存在，请使用 save_douyin_cookie.py 保存 cookie")
        douyin_logger.info("    用法: python save_douyin_cookie.py \"sessionid=xxx; sid_tt=yyy; ...\"")
        return (False, None)

    ok, browser = await cookie_auth(account_file, account_name, reuse_browser=True)
    if ok and browser is not None:
        return (True, browser)
    if not ok:
        if handle:
            browser, tab = await attach_login_chrome()
            douyin_logger.info("[+] cookie 已失效，已打开抖音登录页，请完成扫码登录")
            if await _wait_for_login(browser, account_file, account_name):
                checked_tab = await _browser_get_with_retry(browser, DOUYIN_UPLOAD_URL)
                return (True, (browser, checked_tab))
            return (False, None)
        douyin_logger.info("[+] cookie 已失效，请重新获取 cookie 并用 save_douyin_cookie.py 保存")
        return (False, None)
    return (True, None)


class DouYinVideo(object):
    def __init__(self, title: str, file_path: str, tags: list, publish_date: datetime, account_file: str,
                 thumbnail_path=None, productLink="", productTitle="", description: str = "", account_name: str = "default"):
        self.title = title
        self.file_path = file_path
        self.tags = tags
        self.description = description or ""
        self.publish_date = publish_date
        self.account_file = account_file
        self.account_name = account_name
        self.date_format = "%Y年%m月%d日 %H:%M"
        self.local_executable_path = LOCAL_CHROME_PATH
        self.headless = LOCAL_CHROME_HEADLESS
        self.thumbnail_path = thumbnail_path
        self.productLink = productLink
        self.productTitle = productTitle

    async def set_schedule_time_douyin(self, tab, publish_date: datetime):
        try:
            label = await tab.find("定时发布", best_match=True)
            if label:
                await label.click()
            await tab.sleep(1)
            inp = await tab.select('.semi-input[placeholder="日期和时间"]')
            if inp:
                await inp.click()
                await tab.sleep(0.3)
                await inp.send_keys(publish_date.strftime("%Y-%m-%d %H:%M"))
            await tab.sleep(1)
        except Exception:
            pass

    async def handle_upload_error(self, tab):
        douyin_logger.info("视频出错了，重新上传中")
        inp = await tab.select('div.progress-div input[type="file"]')
        if inp:
            await inp.send_file(self.file_path)

    async def upload(self, browser=None, existing_tab=None) -> bool:
        own_browser = browser is None
        if existing_tab is not None and browser is not None:
            tab = existing_tab
        elif browser is None:
            for try_reuse in (True, False):
                res = await get_browser(headless=self.headless, account_name=self.account_name, try_reuse=try_reuse)
                browser, _ = res if isinstance(res, tuple) else (res, False)
                if need_cookie_file(AUTH_MODE) and os.path.exists(self.account_file):
                    try:
                        await load_cookies_from_file(browser, self.account_file)
                    except Exception:
                        pass
                try:
                    tab = await _browser_get_with_retry(browser, DOUYIN_UPLOAD_URL)
                    break
                except (StopIteration, RuntimeError) as e:
                    if try_reuse:
                        douyin_logger.warning(f"[-] 复用 Chrome 失败 ({e})，改用新浏览器")
                    else:
                        raise
        else:
            tab = await _browser_get_with_retry(browser, DOUYIN_UPLOAD_URL)
        publish_success = False
        try:
            douyin_logger.info(f"[+]正在上传-------{self.title}.mp4")
            douyin_logger.info("[-] 正在打开主页...")
            await tab.sleep(2)

            if "creator-micro/content/upload" not in tab.url:
                douyin_logger.error("[+] 未进入上传页，请检查网络或 cookie")
                return False
            if await _has_text(tab, "手机号登录") or await _has_text(tab, "扫码登录"):
                douyin_logger.error("[+] 未登录，请用 save_douyin_cookie.py 保存 cookie 后重试")
                return False

            upload_inp = await tab.select('div[class^="container"] input[type="file"]')
            if not upload_inp:
                upload_inp = await tab.select('input[type="file"]')
            if upload_inp:
                await upload_inp.send_file(self.file_path)
            else:
                douyin_logger.error("[-] 未找到上传按钮")
                return False

            for _ in range(60):
                await tab.sleep(0.3)
                if "publish" in tab.url or "post/video" in tab.url:
                    douyin_logger.info("[+] 成功进入发布页面!")
                    break
            else:
                douyin_logger.error("[-] 超时未进入视频发布页面")
                return False

            while True:
                await tab.sleep(1)
                if await tab.find("重新上传", best_match=True):
                    douyin_logger.success("[-] 视频上传完毕")
                    break
                if await tab.find("上传失败", best_match=True):
                    await self.handle_upload_error(tab)
                else:
                    douyin_logger.info("[-] 正在上传视频中...")

            if self.productLink and self.productTitle:
                douyin_logger.info("[-] 正在设置商品链接...")
                await self.set_product_link(tab, self.productLink, self.productTitle)
                douyin_logger.info("[+] 完成设置商品链接...")

            await self.apply_cover_strategy(tab)
            await self.clear_blocking_ui(tab)

            await tab.sleep(0.3)
            douyin_logger.info("[-] 正在填充标题和话题...")

            title_inp = await tab.select("input.semi-input-default", timeout=5)
            if not title_inp:
                title_inp = await tab.select('input[placeholder*="标题"]', timeout=5)
            if title_inp:
                await title_inp.click()
                await title_inp.send_keys(self.title[:30])

            desc = await tab.select("div.zone-container.editor", timeout=3) or await tab.select(".zone-container", timeout=3)
            if desc:
                await desc.click()
                if self.description:
                    await desc.send_keys(self.description + " ")
                for tag in self.tags:
                    await desc.send_keys("#" + tag + " ")
            douyin_logger.info(f"文案+话题已填充，共{len(self.tags)}个话题")

            try:
                switch = await tab.select('[class^="info"] [class^="first-part"] div.semi-switch input', timeout=2)
                if switch:
                    await switch.click()
            except Exception:
                pass

            if self.publish_date != 0:
                await self.set_schedule_time_douyin(tab, self.publish_date)

            publish_clicked = False
            for i in range(40):
                should_retry_click = (not publish_clicked) or (i > 0 and i % 12 == 0)
                if should_retry_click and await _click_publish_button(tab):
                    publish_clicked = True
                    douyin_logger.info("[-] 已点击发布按钮")
                await tab.sleep(0.3)
                if "manage" in (tab.url or ""):
                    douyin_logger.success("[-] 视频发布成功")
                    publish_success = True
                    break
                try:
                    need_cover = await tab.find("请设置封面后再发布", best_match=True, timeout=0.5)
                except Exception:
                    need_cover = None
                if need_cover:
                    await self.handle_auto_video_cover(tab)
                    publish_clicked = False
                elif i > 0 and i % 8 == 0:
                    douyin_logger.info(f"[-] 等待发布结果... ({i // 4}s)")
            else:
                douyin_logger.error("[-] 发布流程已触发，但未确认成功")
                return False

            if need_cookie_file(AUTH_MODE):
                try:
                    ok = await asyncio.wait_for(save_cookies_to_json(browser, self.account_file), timeout=5.0)
                    if ok:
                        douyin_logger.success("[-] cookie更新完毕！")
                except (asyncio.TimeoutError, Exception) as e:
                    douyin_logger.warning(f"[-] 保存 cookie 跳过: {e}")
            await tab.sleep(1)
            return publish_success
        finally:
            if publish_success and _nodriver_util:
                try:
                    _nodriver_util.get_registered_instances().discard(browser)
                except Exception:
                    pass
            if own_browser and not publish_success:
                browser.stop()

    async def clear_blocking_ui(self, tab):
        try:
            wrap = await tab.select("div.dy-creator-content-modal-wrap", timeout=1)
            spin = await tab.select("div.dy-creator-content-portal .semi-spin", timeout=1)
            if wrap or spin:
                await tab.evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))")
        except Exception:
            pass

    async def select_ai_cover_dialog(self, tab) -> bool:
        try:
            douyin_logger.info("[-] 选择封面弹窗...")
            sel = await tab.find("选择封面", best_match=True)
            if sel:
                await sel.click()
            await tab.sleep(1)
            for lab in ("AI 封面", "智能封面", "视频帧", "推荐"):
                t = await tab.find(lab, best_match=True, timeout=3)
                if t:
                    await t.click()
                    await tab.sleep(0.3)
                    break
            for _ in range(15):
                cov = None
                for sel in ('[class^="recommendCover-"]', "canvas", "img"):
                    try:
                        cov = await tab.select(sel, timeout=1)
                        if cov:
                            break
                    except Exception:
                        pass
                if cov:
                    await cov.click()
                    await tab.sleep(0.15)
                try:
                    done_btn = await tab.find("完成", best_match=True, timeout=2)
                except Exception:
                    done_btn = None
                if done_btn:
                    await done_btn.click()
                    douyin_logger.success("[+] 封面已确认")
                    await tab.sleep(0.5)
                    await self._confirm_cover_apply_dialog(tab)
                    return True
            return False
        except Exception as e:
            douyin_logger.warning(f"[-] 封面弹窗失败: {e}")
            return False

    async def _confirm_cover_apply_dialog(self, tab):
        for _ in range(5):
            try:
                if await _has_text(tab, "是否确认应用此封面"):
                    ok_btn = await tab.find("确定", best_match=True, timeout=2)
                    if ok_btn:
                        await ok_btn.click()
                        douyin_logger.info("[-] 已确认应用封面")
                        await tab.sleep(0.3)
                        return True
                got_it = await tab.find("我知道了", best_match=True, timeout=1)
                if got_it:
                    await got_it.click()
                    douyin_logger.info("[-] 已关闭「我知道了」提示")
                    await tab.sleep(0.2)
                    continue
                return False
            except Exception:
                pass
            await tab.sleep(0.2)
        return False

    async def dismiss_optional_cover_dialogs(self, tab):
        try:
            btn = await tab.find("暂不设置", best_match=True, timeout=2)
            if btn:
                await btn.click()
                douyin_logger.info("[-] 已关闭横封面相关弹窗")
                await tab.sleep(0.3)
                return True
        except Exception:
            pass
        return False

    async def apply_cover_strategy(self, tab):
        if self.thumbnail_path and os.path.isfile(str(self.thumbnail_path)):
            await self.set_thumbnail(tab, str(self.thumbnail_path))
        else:
            await tab.sleep(1.5)
            if not await self.select_ai_cover_dialog(tab):
                douyin_logger.info("[-] 封面未自动完成")
        await self._confirm_cover_apply_dialog(tab)
        await self.dismiss_optional_cover_dialogs(tab)

    async def handle_auto_video_cover(self, tab):
        try:
            if await tab.find("请设置封面后再发布", best_match=True):
                cov = await tab.select('[class^="recommendCover-"]')
                if cov:
                    await cov.click()
                    await tab.sleep(0.5)
                    confirm = await tab.find("确定", best_match=True)
                    if confirm:
                        await confirm.click()
                    return True
        except Exception:
            pass
        return False

    async def set_thumbnail(self, tab, thumbnail_path: str):
        if not thumbnail_path:
            return
        douyin_logger.info("[-] 正在设置视频封面...")
        sel = await tab.find("选择封面", best_match=True)
        if sel:
            await sel.click()
        await tab.sleep(0.5)
        vert = await tab.find("设置竖封面", best_match=True)
        if vert:
            await vert.click()
        await tab.sleep(1)
        inp = await tab.select("input.semi-upload-hidden-input")
        if inp:
            await inp.send_file(thumbnail_path)
        await tab.sleep(1)
        done = await tab.find("完成", best_match=True)
        if done:
            await done.click()
        douyin_logger.info("[+] 视频封面设置完成！")
        await tab.sleep(0.5)
        await self._confirm_cover_apply_dialog(tab)
        await self.dismiss_optional_cover_dialogs(tab)

    async def set_product_link(self, tab, product_link: str, product_title: str):
        await tab.sleep(1)
        try:
            dropdown = await tab.select(".semi-select")
            if dropdown:
                await dropdown.click()
            await tab.sleep(1)
            cart = await tab.find("购物车", best_match=True)
            if cart:
                await cart.click()
            await tab.sleep(1)
            inp = await tab.select('input[placeholder*="商品链接"]')
            if inp:
                await inp.send_keys(product_link)
            add_btn = await tab.find("添加链接", best_match=True)
            if add_btn:
                await add_btn.click()
            await tab.sleep(1)
            title_inp = await tab.select('input[placeholder*="短标题"]')
            if title_inp:
                await title_inp.send_keys(product_title[:10])
            fin = await tab.find("完成编辑", best_match=True)
            if fin:
                await fin.click()
            return True
        except Exception as e:
            douyin_logger.error(f"[-] 设置商品链接时出错: {e}")
            return False

    async def main(self, browser=None):
        await self.upload(browser=browser)
