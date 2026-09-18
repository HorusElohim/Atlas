from atlas import browser


def test_page_result_captures_title_and_status() -> None:
    result = browser.PageResult(url="https://example.com", title="Example Domain", status=200)

    assert result.url == "https://example.com"
    assert result.title == "Example Domain"
    assert result.status == 200
