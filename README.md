# book-ocr

**0 元、可长期复用的扫描型 PDF / EPUB 全文提取流水线**（GitHub Actions + OCRmyPDF + Tesseract + Poppler）。

目标：尽可能保留整本书的完整文字、页序和章节结构，方便后续检索、翻译、总结与分析（不是只做摘要）。

## 架构

```
手机/本机上传 PDF/EPUB → input/
        ↓ push / workflow_dispatch
GitHub Actions (ubuntu-latest)
        ↓
PDF：有文字层 → pdftotext；扫描件 → OCRmyPDF + Tesseract (chi_sim+eng)
EPUB：解压 OPF/spine → 清理 HTML → TXT + Markdown + 分章
        ↓
output/<书名>/
  book_ocr.pdf      # 可搜索 PDF（PDF 输入）
  book.txt          # 完整连续文本
  pages/0001.txt …  # 按页/章分片（避免 MCP 截断）
  manifest.json     # 页数、字符数、异常页、分片数
  ocr_errors.txt    # 低文字量页（如有）
```

## 使用方法

1. 把 PDF 或 EPUB 放到 `input/`（**私人书籍请用私有仓库或不要 push 原书到公开仓**；本仓库代码可公开）。
2. Push 到 `main`，或在 Actions 页手动 **Run workflow**。
3. 结束后在 `output/<文件名不含扩展名>/` 查看结果；先读 `manifest.json` 核对完整性，再按 `pages/` 顺序读取。

### 手动触发参数

| 参数 | 说明 |
|------|------|
| `file` | 只处理 `input/` 下某个文件名；空=全部 |
| `lang` | 默认 `chi_sim+eng`；繁体可用 `chi_tra` / `chi_tra+eng` |
| `force_ocr` | `true` 时即使已有文字层也强制 OCR |

## 本地运行（可选）

```bash
# Debian/Ubuntu 示例
sudo apt-get install ocrmypdf tesseract-ocr tesseract-ocr-chi-sim \
  tesseract-ocr-eng poppler-utils ghostscript qpdf
python scripts/process_book.py --lang chi_sim+eng
```

## 设计原则（与 Notion 方案一致）

- **先判断文字层**，避免对电子 PDF 无脑 OCR。
- **不要只依赖一个超大 TXT**：必须有分片 + `manifest.json`，方便 GitHub MCP / ChatGPT 完整读取。
- OCR **不承诺 100% 准确**；异常页写入 `ocr_errors.txt`。
- Actions **仅在 `input/**` push 或手动触发时运行**，不设高频定时，控制免费额度。
- 代码可公开；**原书文件不应进公开仓库**。

## 输出 manifest 示例字段

```json
{
  "source_file": "mybook.pdf",
  "total_pages": 428,
  "ocr_success": 426,
  "ocr_suspect": 2,
  "text_chars": 385421,
  "chunks": 428,
  "ocr_language": "chi_sim+eng",
  "had_text_layer": false,
  "ocr_mode": "ocr"
}
```

## License

MIT（工具链均为开源：OCRmyPDF、Tesseract、Poppler 等）。
