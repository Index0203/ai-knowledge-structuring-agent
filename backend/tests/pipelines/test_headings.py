from app.pipelines.document_processing.headings import (
    TextLine,
    detect_heading_level,
    detect_visual_heading_level,
    is_noise_line,
    is_table_of_contents,
    looks_like_unlabelled_chapter_opener,
    next_chapter_prefix,
    next_expected_label,
    normalize_heading_text,
    repair_label,
    label_title,
    reattach_trailing_markers,
    split_inline_items,
    split_numbered_item,
    split_noise_label,
    split_label_heading,
    strip_opener_noise,
)


def test_chinese_and_numeric_headings_map_to_outline_levels() -> None:
    assert detect_heading_level("第二章 数智聚焦，助推专业深耕再进阶") == 1
    assert detect_heading_level("第一节 数据底座") == 2
    assert detect_heading_level("一、数字化知识库构建") == 2
    assert detect_heading_level("（二）平台载体建设") == 3
    assert detect_heading_level("1.1 总体架构") == 3
    assert detect_heading_level("1.优化包装策略") == 4
    assert detect_heading_level("2、构建弹性物流合作机制") == 4
    assert detect_heading_level("Chapter 2 Digital services") == 1


def test_body_lines_are_not_headings() -> None:
    assert detect_heading_level("企业通过引入智能排产系统提升了生产效率，成本降低 15%。") is None
    assert detect_heading_level("一、这一条其实是正文，因为它以句号结尾。") is None
    # A decimal keeps its decimal level; it must not be read as a `1.` section item.
    assert detect_heading_level("1.5 亿元的市场规模") != 4
    assert detect_heading_level("") is None
    assert detect_heading_level("很长的一行正文" * 20) is None


def test_font_size_hints_only_apply_to_distinct_sizes() -> None:
    body_size = 10.0

    assert detect_visual_heading_level(TextLine("第一章 总论", 18.0), body_size) == 1
    assert detect_visual_heading_level(TextLine("一、背景", 13.5), body_size) == 2
    assert detect_visual_heading_level(TextLine("（一）细节", 12.0), body_size) == 3
    assert detect_visual_heading_level(TextLine("普通正文", 10.0), body_size) is None
    assert detect_visual_heading_level(TextLine("没有字号信息"), None) is None


def test_heading_text_is_normalised() -> None:
    assert normalize_heading_text("  第二章   数智聚焦  ") == "第二章 数智聚焦"


def test_contents_pages_are_recognised() -> None:
    contents = [
        TextLine("第一章 时代坐标下的专精特新企业 ......... 4"),
        TextLine("第二章 数智聚焦，助推专业深耕再进阶 ........ 13"),
        TextLine("一、数字化知识库构建 ........ 14"),
    ]
    body = [
        TextLine("第一章 时代坐标下的专精特新企业"),
        TextLine("企业通过数智化转型提升了生产效率，成本降低 15%。"),
        TextLine("本章介绍了相关的实践案例。"),
    ]

    assert is_table_of_contents(contents) is True
    assert is_table_of_contents(body) is False


def test_short_pages_are_never_treated_as_contents() -> None:
    assert is_table_of_contents([TextLine("第一章 总论 ........ 2")]) is False


def test_years_and_plain_text_are_not_dot_leaders() -> None:
    body = [
        TextLine("截至 2026 年，我国累计培育专精特新中小企业超 14 万家。"),
        TextLine("第一章 总论"),
        TextLine("本章讨论总体情况。"),
    ]

    assert is_table_of_contents(body) is False


def test_page_numbers_and_rulers_are_layout_noise() -> None:
    assert is_noise_line("- 13 -") is True
    assert is_noise_line("17") is True
    assert is_noise_line(".........") is True
    assert is_noise_line("第二章 数智聚焦") is False


def test_ocr_confused_numerals_still_mark_bracketed_headings() -> None:
    # Tesseract reads 二 as "=" and 一 as "I"/"l" on this scanned document.
    assert detect_heading_level("(=) 梯度赋能筑数转格局，科学评测促高质量发展") == 3
    assert detect_heading_level("（I）总体概览") == 3
    assert detect_heading_level("(l) 总体概览") == 3
    # Real words inside brackets must not become headings.
    assert detect_heading_level("（AI）技术应用") is None


def test_confused_numeral_is_repaired_in_the_heading_title() -> None:
    assert normalize_heading_text("(=) 梯度赋能筑数转格局，科学评测促高质量发展") == (
        "(二) 梯度赋能筑数转格局，科学评测促高质量发展"
    )
    assert normalize_heading_text("（I）总体概览") == "（一）总体概览"
    # Body text must never be rewritten.
    assert normalize_heading_text("2026 年产值增长 = 15%") == "2026 年产值增长 = 15%"


def test_decimal_numbers_in_body_text_are_not_headings() -> None:
    assert detect_heading_level("2.6 倍; 研发人员占比达 25.1%; 户均拥有发明专利 26.6") is None
    assert detect_heading_level("1.1 总体架构") == 3


def test_bracket_numbering_tolerates_stray_spaces() -> None:
    # The scan produced "(三 ) 社会贡献持续活跃", which used to be skipped entirely.
    assert detect_heading_level("(三 ) 社会贡献持续活跃") == 3
    assert detect_heading_level("（ 二 ）梯度赋能筑数转格局") == 3


def test_inline_label_headings_are_split_from_their_body() -> None:
    label, body = split_label_heading("传统发展痛点: (1) 合作模式层面: 被动配套依附性强") or ("", "")

    assert label == "传统发展痛点"
    assert body == "(1) 合作模式层面: 被动配套依附性强"
    assert split_label_heading("这是一句普通正文，包含冒号: 但不是标签") is None


def test_stylised_chapter_opener_is_detected() -> None:
    opener = looks_like_unlabelled_chapter_opener(
        [
            "SAB 数智致远，璧画专精特新发展新图景",
            "一、数智技术融合加速深化",
            "二、企业成长模式迭代升级",
            "三、产业生态协同更加紧密",
        ]
    )
    ordinary_page = looks_like_unlabelled_chapter_opener(
        [
            "专精特新中小企业营业收入持续增长，规模不断扩大。",
            "从区域分布看，东部地区企业数量占比最高。",
            "中部地区次之，西部地区增速较快。",
        ]
    )

    assert opener == "SAB 数智致远，璧画专精特新发展新图景"
    assert ordinary_page is None


def test_unlabelled_opener_continues_the_chapter_numbering() -> None:
    assert next_chapter_prefix("第五章 数智创新，引领产业变革新方向") == "第六章"
    assert next_chapter_prefix("第九章 技术展望") == "第十章"
    assert next_chapter_prefix("前言") == ""
    assert next_chapter_prefix(None) == ""


def test_opener_is_found_below_trailing_body_lines() -> None:
    lines = [
        "销服务一体化平台，实现营销过程和服务过程的数字化管理",
        "SAB 数智致远，璧画专精特新发展新图景",
        "一、数智技术融合加速深化",
        "技术融合持续推进。",
        "二、企业成长模式迭代升级",
        "企业模式持续升级。",
    ]

    assert looks_like_unlabelled_chapter_opener(lines) == "SAB 数智致远，璧画专精特新发展新图景"


def test_arabic_bracket_items_are_fourth_level() -> None:
    assert detect_heading_level("(1) 数据底座层面: 老师传经验系统性梳理") == 4
    assert detect_heading_level("（2）平台载体层面: 搭建大数据研判模型") == 4
    # Chinese numbering stays at the third level.
    assert detect_heading_level("（三）推动“人工智能+”融合应用") == 3


def test_opener_noise_is_stripped() -> None:
    assert strip_opener_noise("SAB 数智致远，璧画专精特新发展新图景") == "数智致远，璧画专精特新发展新图景"
    assert strip_opener_noise("28 数智致远") == "数智致远"
    assert strip_opener_noise("数智致远，璧画专精特新发展新图景") == "数智致远，璧画专精特新发展新图景"


def test_label_separator_can_be_a_semicolon() -> None:
    label, body = split_label_heading("数智化赋能成效; 形成具备高精准性、高时效性的赛道研判体系") or ("", "")

    assert label == "数智化赋能成效"
    assert body.startswith("形成具备高精准性")


def test_mangled_labels_are_recognised_as_labels() -> None:
    assert split_noise_label("RRR RB: (1) 知识传承: 技术经验依附个体，") is not None
    assert split_noise_label("BE ACN RE: 形成具备高耦合性、高粘性壁垒") is not None
    # Ordinary prose with a comma is not a label.
    assert split_noise_label("经济方面，专精特新中小企业经营规模逐年扩大，在") is None


def test_expected_label_sequence_repairs_garbled_labels() -> None:
    assert next_expected_label(set()) == "传统发展痛点"
    assert next_expected_label({"传统发展痛点", "数智化赋能路径"}) == "数智化赋能成效"
    assert next_expected_label({"传统发展痛点", "数智化赋能路径", "数智化赋能成效"}) is None


def test_garbled_label_is_identified_from_its_wording() -> None:
    # "形成 …" is an outcome description, so the garbled label is 成效, not 路径.
    assert repair_label({"传统发展痛点"}, "形成高耦合性的产业链协同体系") == "数智化赋能成效"
    assert repair_label(set(), "(1) 知识传承: 技术经验依附个体") == "传统发展痛点"


def test_repeated_case_studies_are_named_after_their_case() -> None:
    assert label_title("典型案例", "长飞光纤一一工业互联网平台赋能全产业链协同") == (
        "典型案例：长飞光纤一一工业互联网平台赋能全产业链协同"
    )
    assert label_title("典型案例", "圣昊光电是国家级专精特新“小巨人”企业，针对光芯片…") == (
        "典型案例：圣昊光电是国家级专精特新“小巨人”企业"
    )
    assert label_title("传统发展痛点", "(1) 知识传承") == "传统发展痛点"


def test_inline_numbered_items_are_split_into_their_own_lines() -> None:
    parts = split_inline_items(
        "传统发展痛点: (1) 知识传承: 技术经验依附个体，资产留存风险极高; (2) 技术优化: 迭代效率低; (3) 系统匹配: 适配不足"
    )

    assert parts == [
        "传统发展痛点:",
        "(1) 知识传承: 技术经验依附个体，资产留存风险极高;",
        "(2) 技术优化: 迭代效率低;",
        "(3) 系统匹配: 适配不足",
    ]
    # Ordinary prose keeps its numbering inline.
    assert split_inline_items("本章共有 3 个方面（1）甲（2）乙") == ["本章共有 3 个方面（1）甲（2）乙"]


def test_numbered_items_become_a_short_title_plus_body() -> None:
    assert split_numbered_item("(3) 系统匹配: 通用数字化系统适配不足，工艺经验落地") == (
        "(3) 系统匹配",
        "通用数字化系统适配不足，工艺经验落地",
    )
    assert split_numbered_item("（一）没有内层标签时整行即标题与正文") == (
        "（一）没有内层标签时整行即标题与正文",
        "（一）没有内层标签时整行即标题与正文",
    )


def test_marker_at_the_end_of_a_line_moves_to_the_next_line() -> None:
    repaired = reattach_trailing_markers(
        [
            TextLine("促进技术沉淀; (2)"),
            TextLine("固化为算法模型，隐性知识模型化"),
            TextLine("(3) 长效运营层面: 跨系统集成与整合"),
        ]
    )

    assert [line.text for line in repaired] == [
        "促进技术沉淀;",
        "(2) 固化为算法模型，隐性知识模型化",
        "(3) 长效运营层面: 跨系统集成与整合",
    ]


def test_inline_split_tolerates_a_space_inside_the_marker() -> None:
    parts = split_inline_items("完善基础; (2) 平台载体层面: 搭建模型; (3 ) 长效运营层面: 构建闭环")

    assert parts == [
        "完善基础;",
        "(2) 平台载体层面: 搭建模型;",
        "(3 ) 长效运营层面: 构建闭环",
    ]
