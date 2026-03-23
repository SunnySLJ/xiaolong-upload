# -*- coding: utf-8 -*-
"""
抖音创作者平台上传 - 纯 CDP（nodriver）

登录授权模式（conf.AUTH_MODE）：
  cookie  - 从 cookie 文件加载登录态，无登录流程；支持 Connect 脚本 + CDP 连接
  connect - 连接已有 Chrome（须先运行 scripts/open_chrome_for_upload.sh）
  profile - 固定用户目录，登录态保存
"""
from datetime import datetime
import os
import asyncio

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

from conf import LOCAL_CHROME_PATH, LOCAL_CHROME_HEADLESS, AUTH_MODE
from douyin.browser import get_browser, try_connect_existing_chrome
from common.utils import need_cookie_file
from common.loggers import douyin_logger

# 发布成功时从 nodriver 的 atexit 清理列表中移除，避免脚本退出时被关闭
try:
    from nodriver.core import util as _nodriver_util
except ImportError:
    _nodriver_util = None


# ==================== 工具函数 ====================
from common.utils import has_text_in_page as _has_text


# ==================== 登录与校验 ====================

async def _check_logged_in(browser, account_file: str, account_name: str) -> bool:
    """访问上传页，校验是否已登录抖音创作者中心"""
    # cookie 模式：先加载已保存的 cookie
    if need_cookie_file(AUTH_MODE) and os.path.exists(account_file):
        try:
            await browser.cookies.load(account_file)
        except Exception:
            pass

    tab = await browser.get("https://creator.douyin.com/creator-micro/content/upload")
    await tab.sleep(2)

    # 未进入上传页说明可能被重定向到登录
    if "creator.douyin.com/creator-micro/content/upload" not in tab.url:
        douyin_logger.info("[+] 未进入上传页，可能需重新登录")
        return False

    # 页面上有登录入口说明未登录
    if await _has_text(tab, "手机号登录") or await _has_text(tab, "扫码登录"):
        douyin_logger.info("[+] 检测到登录页，cookie/会话已失效")
        return False

    douyin_logger.info("[+] 已登录")
    return True


async def cookie_auth(account_file: str, account_name: str = "default", reuse_browser: bool = False):
    """
    校验登录态。返回 (是否已登录, 可复用的 browser 或 None)。
    当 reuse_browser=True 且已登录时，不关闭浏览器，返回 (True, browser) 供后续复用。
    """
    for try_reuse in (True, False):
        res = await get_browser(
            headless=LOCAL_CHROME_HEADLESS, account_name=account_name, try_reuse=try_reuse
        )
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
    """
    登录预备：若已登录返回 (True, browser)；若未登录且 handle=True 则引导扫码后返回 (True, browser)。
    返回的 browser 供上传复用，调用方负责在流程结束后停止。

    cookie 模式：直接走 cookie_auth，不调用 try_connect_existing_chrome（避免误关 Connect 脚本启动的 Chrome）
    """
    # connect/profile 模式：优先尝试连接已打开的 Chrome
    if not need_cookie_file(AUTH_MODE):
        existing = await try_connect_existing_chrome()
        if existing:
            douyin_logger.info("[+] 已连接并复用已有浏览器")
            return (True, existing)  # (browser, tab) 已在发布页

    if need_cookie_file(AUTH_MODE) and not os.path.exists(account_file):
        if not handle:
            douyin_logger.info("[+] cookie 文件不存在，请先登录（handle=True）")
            return (False, None)
    else:
        ok, browser = await cookie_auth(account_file, account_name, reuse_browser=True)
        if ok and browser is not None:
            return (True, browser)

    if not handle:
        return (False, None)

    douyin_logger.info("[+] 需要登录，即将打开浏览器...")
    res = await douyin_cookie_gen(account_file, account_name)
    # douyin_cookie_gen 返回 (browser, tab)，tab 已在发布页
    if isinstance(res, tuple) and len(res) == 2:
        return (True, res)
    return (True, (res, None))  # 兼容旧返回值


async def _is_login_page(tab) -> bool:
    """检测当前 tab 是否在登录页（需扫码）"""
    url = (tab.url or "").lower()
    if "creator-micro/content/upload" in url:
        return False
    if "login" in url or "passport" in url:
        return True
    if await _has_text(tab, "手机号登录", timeout=1):
        return True
    if await _has_text(tab, "扫码登录", timeout=1):
        return True
    return False


async def douyin_cookie_gen(account_file: str, account_name: str = "default"):
    """打开浏览器，等待用户扫码登录，登录成功后自动检测并保存。返回 browser 供复用。"""
    was_reused = False
    for try_reuse in (True, False):
        res = await get_browser(headless=False, account_name=account_name, try_reuse=try_reuse)
        browser, was_reused = res if isinstance(res, tuple) else (res, False)
        try:
            tab = await browser.get("https://creator.douyin.com/")
            break
        except (StopIteration, RuntimeError) as e:
            if try_reuse:
                douyin_logger.warning(f"[-] 复用 Chrome 失败 ({e})，改用新浏览器")
            else:
                raise

    await tab.sleep(2)
    if AUTH_MODE == "connect":
        douyin_logger.info("[+] 已连接你的 Chrome，请在浏览器中扫码登录抖音创作者中心")
    else:
        douyin_logger.info("[+] 请在浏览器中扫码登录，登录成功约 15 秒内会自动检测")

    upload_url = "https://creator.douyin.com/creator-micro/content/upload"
    poll_interval = 15
    max_wait = 600
    for elapsed in range(0, max_wait, poll_interval):
        await tab.sleep(poll_interval)
        try:
            tab = await browser.get(upload_url)
        except (StopIteration, RuntimeError):
            continue
        await tab.sleep(2)
        if not await _is_login_page(tab):
            douyin_logger.info("[+] 检测到已登录，正在保存...")
            break
        douyin_logger.info(f"[-] 等待登录中... ({elapsed + poll_interval}s)")
    else:
        douyin_logger.error("[-] 登录超时")
        if not was_reused:
            browser.stop()
        raise TimeoutError("登录超时，请重试")

    if need_cookie_file(AUTH_MODE):
        try:
            cookie_dir = os.path.dirname(account_file)
            os.makedirs(cookie_dir, exist_ok=True)
            douyin_logger.info("[-] 保存 cookie...")
            await asyncio.wait_for(browser.cookies.save(account_file), timeout=5.0)
            douyin_logger.info("[+] 登录信息已保存")
        except (asyncio.TimeoutError, Exception) as e:
            douyin_logger.warning(f"[-] 保存 cookie 跳过: {e}")
    else:
        douyin_logger.info("[+] 登录态已保存（profile/当前会话）")

    douyin_logger.info("[+] 已在发布页，准备进入上传流程")
    return (browser, tab)  # 返回已在发布页的 tab，避免 upload 时再次 get 丢失会话


# ==================== 上传主逻辑 ====================

class DouYinVideo(object):
    """抖音视频上传任务封装"""

    def __init__(
        self,
        title: str,
        file_path: str,
        tags: list,
        publish_date: datetime,
        account_file: str,
        thumbnail_path=None,
        productLink="",
        productTitle="",
        description: str = "",
        account_name: str = "default",
    ):
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
        """设置定时发布时间"""
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
        """视频上传失败时，点击重新上传"""
        douyin_logger.info("视频出错了，重新上传中")
        inp = await tab.select('div.progress-div input[type="file"]')
        if inp:
            await inp.send_file(self.file_path)

    async def upload(self, browser=None, existing_tab=None) -> None:
        """执行完整上传流程。若传入 browser 则复用；若有 existing_tab（已在发布页）则直接用。"""
        own_browser = browser is None
        if existing_tab is not None and browser is not None:
            tab = existing_tab
        elif browser is None:
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
                    tab = await browser.get("https://creator.douyin.com/creator-micro/content/upload")
                    break
                except (StopIteration, RuntimeError) as e:
                    if try_reuse:
                        douyin_logger.warning(f"[-] 复用 Chrome 失败 ({e})，改用新浏览器")
                    else:
                        raise
        else:
            # 有 browser 但无 existing_tab，需要导航到发布页
            tab = await browser.get("https://creator.douyin.com/creator-micro/content/upload")
        publish_success = False
        try:
            douyin_logger.info(f"[+]正在上传-------{self.title}.mp4")
            douyin_logger.info("[-] 正在打开主页...")
            await tab.sleep(2)

            if "creator-micro/content/upload" not in tab.url:
                douyin_logger.error("[+] 未进入上传页，请检查网络或 cookie")
                return
            if await _has_text(tab, "手机号登录") or await _has_text(tab, "扫码登录"):
                douyin_logger.error("[+] 未登录，请先运行并完成扫码登录")
                return

            # 1. 选择视频文件并上传
            upload_inp = await tab.select('div[class^="container"] input[type="file"]')
            if not upload_inp:
                upload_inp = await tab.select('input[type="file"]')
            if upload_inp:
                await upload_inp.send_file(self.file_path)
            else:
                douyin_logger.error("[-] 未找到上传按钮")
                return

            # 2. 等待进入发布页（URL 变化）
            for _ in range(60):
                await tab.sleep(0.3)
                if "publish" in tab.url or "post/video" in tab.url:
                    douyin_logger.info("[+] 成功进入发布页面!")
                    break
            else:
                douyin_logger.error("[-] 超时未进入视频发布页面")
                return

            # 3. 等待视频转码/上传完成（出现「重新上传」表示完成）
            while True:
                await tab.sleep(1)
                if await tab.find("重新上传", best_match=True):
                    douyin_logger.success("[-] 视频上传完毕")
                    break
                if await tab.find("上传失败", best_match=True):
                    await self.handle_upload_error(tab)
                else:
                    douyin_logger.info("[-] 正在上传视频中...")

            # 4. 可选：设置商品链接（带货）
            if self.productLink and self.productTitle:
                douyin_logger.info("[-] 正在设置商品链接...")
                await self.set_product_link(tab, self.productLink, self.productTitle)
                douyin_logger.info("[+] 完成设置商品链接...")

            # 5. 封面策略：自定义封面 or AI 自动选封面
            await self.apply_cover_strategy(tab)
            await self.clear_blocking_ui(tab)

            # 6. 填充标题、文案、话题
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

            # 7. 可选：头条/西瓜同步开关
            try:
                switch = await tab.select('[class^="info"] [class^="first-part"] div.semi-switch input', timeout=2)
                if switch:
                    await switch.click()
            except Exception:
                pass

            # 8. 可选：定时发布
            if self.publish_date != 0:
                await self.set_schedule_time_douyin(tab, self.publish_date)

            # 9. 点击发布，等待跳转到管理页（最多 12 秒后退出，脚本结束后 PowerShell 会关闭浏览器）
            for i in range(40):
                try:
                    pub_btn = await tab.find("发布", best_match=True, timeout=1 if i > 0 else 5)
                except Exception:
                    pub_btn = None
                if pub_btn:
                    await pub_btn.click()
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
                elif i > 0 and i % 8 == 0:
                    douyin_logger.info(f"[-] 等待发布结果... ({i // 4}s)")
            else:
                douyin_logger.info("[-] 发布已提交，即将退出")

            if need_cookie_file(AUTH_MODE):
                try:
                    await asyncio.wait_for(browser.cookies.save(self.account_file), timeout=5.0)
                    douyin_logger.success("[-] cookie更新完毕！")
                except (asyncio.TimeoutError, Exception) as e:
                    douyin_logger.warning(f"[-] 保存 cookie 跳过: {e}")
            await tab.sleep(1)
        finally:
            if publish_success:
                # 从 nodriver atexit 注册表移除，避免脚本退出时 deconstruct_browser 关闭
                if _nodriver_util:
                    try:
                        _nodriver_util.get_registered_instances().discard(browser)
                    except Exception:
                        pass
            # 发布成功时不关闭浏览器；仅失败且为自建 browser 时清理
            if own_browser and not publish_success:
                browser.stop()

    async def clear_blocking_ui(self, tab):
        """关闭可能阻挡操作的加载遮罩"""
        try:
            wrap = await tab.select("div.dy-creator-content-modal-wrap", timeout=1)
            spin = await tab.select("div.dy-creator-content-portal .semi-spin", timeout=1)
            if wrap or spin:
                await tab.evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))")
        except Exception:
            pass

    async def select_ai_cover_dialog(self, tab) -> bool:
        """通过封面弹窗选择 AI 封面"""
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
                    # 点击完成后会弹出「是否确认应用此封面？」需点「确定」
                    await self._confirm_cover_apply_dialog(tab)
                    return True
            return False
        except Exception as e:
            douyin_logger.warning(f"[-] 封面弹窗失败: {e}")
            return False

    async def _confirm_cover_apply_dialog(self, tab):
        """处理「是否确认应用此封面？」弹窗：点击「确定」确认封面"""
        for _ in range(5):
            try:
                if await _has_text(tab, "是否确认应用此封面"):
                    ok_btn = await tab.find("确定", best_match=True, timeout=2)
                    if ok_btn:
                        await ok_btn.click()
                        douyin_logger.info("[-] 已确认应用封面")
                        await tab.sleep(0.3)
                        return True
                # 若有「我知道了」小提示框，先关掉
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
        """关闭「暂不设置」等横版封面可选弹窗（仅此一步，避免过度关闭）"""
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
        """封面策略：有自定义封面用自定义，否则走 AI 自动选封面"""
        if self.thumbnail_path and os.path.isfile(str(self.thumbnail_path)):
            await self.set_thumbnail(tab, str(self.thumbnail_path))
        else:
            await tab.sleep(1.5)
            if not await self.select_ai_cover_dialog(tab):
                douyin_logger.info("[-] 封面未自动完成")
        # 封面流程结束后：先处理「是否确认应用此封面？」，再执行一步关闭残留弹窗
        await self._confirm_cover_apply_dialog(tab)
        await self.dismiss_optional_cover_dialogs(tab)

    async def handle_auto_video_cover(self, tab):
        """发布时若提示需设置封面，自动选一个封面并确定"""
        if await tab.find("请设置封面后再发布", best_match=True):
            cov = await tab.select('[class^="recommendCover-"]')
            if cov:
                await cov.click()
                await tab.sleep(0.5)
                confirm = await tab.find("确定", best_match=True)
                if confirm:
                    await confirm.click()
                return True
        return False

    async def set_thumbnail(self, tab, thumbnail_path: str):
        """上传自定义封面图"""
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
        """设置商品链接（带货视频）"""
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
        """对外入口，与 upload 一致"""
        await self.upload(browser=browser)
