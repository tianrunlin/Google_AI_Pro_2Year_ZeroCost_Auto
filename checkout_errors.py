"""Recognize explicit subscription refusals and stop without retrying payment."""

import re


class CheckoutUnavailable(RuntimeError):
    pass


def checkout_unavailable_reason(visible_text: str) -> str:
    refused = re.search(
        r"^\s*(?:不可订阅|无法订阅|不能订阅|can't subscribe|cannot subscribe|unable to subscribe|subscription unavailable)[。.!]?\s*$",
        visible_text, flags=re.IGNORECASE | re.MULTILINE,
    )
    if not refused:
        return ""
    if "youtube premium individual add on" in visible_text.casefold():
        return "Google 拒绝订阅：YouTube Premium Individual Add On 无法使用，当前套餐组合不可订阅。已停止重试，请在官方页面确认账号可订阅的套餐和实际价格。"
    return "Google 明确提示当前套餐不可订阅。已停止重试，请在官方页面查看可用套餐及限制。"
