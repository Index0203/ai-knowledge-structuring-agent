from app.agents.knowledge_extraction.text_digest import (
    document_term_counts,
    extract_keywords,
    has_content,
    summarize,
)


def test_summary_is_a_single_short_sentence() -> None:
    text = (
        "随着优质中小企业梯度培育体系深化，专精特新企业创新能力加速跃升。"
        "我国累计培育专精特新中小企业超过 14 万家。"
        "各地陆续出台配套政策。"
    )

    result = summarize(text)

    assert result.endswith("。")
    assert result.count("。") == 1
    assert len(result) <= 80


def test_summary_prefers_the_most_representative_sentence() -> None:
    text = (
        "本章介绍背景。"
        "数据协同包含数据底座、平台载体与长效运营三个层面，需要打通信息链路。"
        "数据协同的目标是破除联动壁垒。"
    )

    assert "数据协同" in summarize(text)


def test_keywords_are_domain_terms_not_function_words() -> None:
    text = "数据协同是核心。数据协同需要数据底座。平台载体同样重要。"

    keywords = extract_keywords(text, limit=4)

    assert "数据协同" in keywords
    assert all(keyword not in {"的", "是", "和", "需要"} for keyword in keywords)
    assert len(keywords) == len(set(keywords))


def test_keywords_use_document_frequency_to_break_ties() -> None:
    counts = document_term_counts(["数据协同与平台载体", "数据协同与长效运营"])

    keywords = extract_keywords("数据协同 平台载体 长效运营", document_counts=counts, limit=3)

    # 「数据协同」 appears in every section, so it outranks equally frequent single-section terms.
    assert keywords[0] == "数据协同"


def test_keywords_respect_the_limit_and_empty_text() -> None:
    assert extract_keywords("", limit=3) == []
    assert len(extract_keywords("数据底座 平台载体 长效运营 生态协同", limit=2)) <= 2


def test_page_number_fragments_have_no_content() -> None:
    assert has_content("- 17 -") is False
    assert has_content("●●●") is False
    assert has_content("专精特新企业") is True
    assert has_content("evidence retrieval handbook") is True


def test_keywords_do_not_split_a_phrase_the_document_states_whole() -> None:
    text = "专精特新是核心定位，专精特新中小企业培育体系不断完善。"

    keywords = extract_keywords(text, limit=6)

    assert "专精特新" in keywords
    assert not any(keyword in {"专精", "精特", "特新"} for keyword in keywords)


def test_summary_drops_the_stray_character_glued_by_ocr() -> None:
    text = "业 专业化是指专注核心业务，提高专业化生产、服务和协作配套的能力。企业聚焦细分市场。"

    result = summarize(text)

    assert result.startswith("专业化是指")
    assert len(result) <= 80


def test_summary_prefers_a_definition_sentence() -> None:
    text = (
        "近年来各地持续出台配套政策，培育体系不断完善。"
        "数据显示企业数量稳步增长，区域分布更加均衡。"
        "特色化是指利用特色资源，弘扬传统技艺和地域文化，采用独特工艺、技术、配方或原料。"
    )

    assert summarize(text).startswith("特色化是指")
