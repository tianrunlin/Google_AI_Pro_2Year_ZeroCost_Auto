"""Detect authentication failures without treating security challenges as success."""

from urllib.parse import urlparse


class ManualLoginRequired(RuntimeError):
    pass


MANUAL_LOGIN_HELP = "请点击该账号的「浏览器」按钮，在独立窗口中手动登录并完成 Google 安全验证；关闭该独立窗口后，从 Step 1 重新执行。"


def is_google_auth_page(url: str) -> bool:
    return urlparse(url).hostname in ("accounts.google.com", "gds.google.com")


def login_block_reason(url: str, body: str) -> str:
    if not is_google_auth_page(url):
        return ""
    text = body.casefold().replace("’", "'").replace("‘", "'")
    path = urlparse(url).path.lower()
    if "signin/rejected" in path or any(s in text for s in (
        "we couldn't verify it's you", "couldn't sign you in", "could not sign you in",
        "this browser or app may not be secure", "无法验证您的身份", "无法验证是您本人",
        "此浏览器或应用可能不安全", "无法让您登录",
    )):
        return "Google 拒绝了本次登录，身份验证尚未完成。"
    if "challenge/recaptcha" in path or "证明您不是自动程序" in body or "not a robot" in text:
        return "Google 要求人机验证，需要人工完成。"
    if "add 2-step verification" in text:
        return "Google 要求设置两步验证，需要人工处理。"
    return ""
