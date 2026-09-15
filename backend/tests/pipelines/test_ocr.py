import fitz
from PIL import Image

from app.pipelines.document_processing.ocr import ocr_text_score, render_page_image


def build_page_with_text() -> fitz.Page:
    pdf_document = fitz.open()
    page = pdf_document.new_page(width=595, height=842)
    page.insert_text((72, 120), "Retrieval keeps evidence.", fontsize=12)
    return page


def test_render_page_image_uses_the_requested_dpi() -> None:
    image = render_page_image(build_page_with_text(), 300)

    assert isinstance(image, Image.Image)
    # A4 at 72 dpi is ~595 px wide, so 300 dpi must be several times larger.
    assert image.width > 2000


def test_render_page_image_can_binarize_a_page() -> None:
    image = render_page_image(build_page_with_text(), 150, binarize=True, binarize_threshold=165)

    colors = {color for _count, color in image.convert("L").getcolors(maxcolors=1_000_000)}
    assert colors <= {0, 255}


def test_ocr_result_with_chapter_markers_beats_a_longer_but_flat_result() -> None:
    with_chapter = "第四章 数智突围，构建竞争壁垒新优势\n一、数字定制打造产品特色"
    flat_but_longer = "本章围绕产品特色展开论述。" * 20

    assert ocr_text_score(with_chapter) > ocr_text_score(flat_but_longer)


def test_ocr_score_prefers_more_structure_then_more_text() -> None:
    fewer_chapters = "第三章 数智精益\n正文内容一"
    more_chapters = "第三章 数智精益\n第四章 数智突围\n正文内容一"
    more_text = "第三章 数智精益\n正文内容一二三四五六七八九十"

    assert ocr_text_score(more_chapters) > ocr_text_score(fewer_chapters)
    assert ocr_text_score(more_text) > ocr_text_score(fewer_chapters)
