# test_pubmed_parser.py — PubMed + bioRxiv 解析器单元测试
import json
import pytest
from lib.parsers.pubmed_parser import parse


# ===== PubMed fixtures =====

ESEARCH_XML = """<?xml version="1.0"?>
<eSearchResult>
<Count>3</Count>
<IdList>
<Id>39001234</Id>
<Id>39001235</Id>
<Id>39001236</Id>
</IdList>
</eSearchResult>"""

ESUMMARY_XML = """<?xml version="1.0"?>
<eSummaryResult>
<DocSum>
<Id>39001234</Id>
<Item Name="Title" Type="String">Deep Learning for Drug Discovery</Item>
<Item Name="Author" Type="String">Smith J</Item>
<Item Name="Author" Type="String">Zhang W</Item>
<Item Name="Abstract" Type="String">We propose a novel deep learning framework for molecular property prediction.</Item>
</DocSum>
<DocSum>
<Id>39001235</Id>
<Item Name="Title" Type="String">Graph Neural Networks for Protein Folding</Item>
<Item Name="Author" Type="String">Lee K</Item>
<Item Name="Abstract" Type="String">This paper introduces a GNN-based approach to protein structure prediction.</Item>
</DocSum>
</eSummaryResult>"""


# ===== bioRxiv fixtures =====

BIORXIV_JSON = json.dumps({
    "collection": [
        {
            "title": "Single-cell RNA-seq analysis of brain tissue",
            "abstract": "We present a comprehensive single-cell transcriptomic atlas of the human brain.",
            "doi": "10.1101/2026.07.10.123456",
            "authors": "Brown A; Wilson B; Davis C",
            "category": "neuroscience"
        },
        {
            "title": "CRISPR-Cas9 gene editing in primary cells",
            "abstract": "An optimized protocol for efficient CRISPR editing in primary human cells.",
            "doi": "10.1101/2026.07.10.789012",
            "authors": "Martinez R; Chen L",
            "category": "genetics"
        }
    ]
})

BIORXIV_EMPTY = json.dumps({"collection": []})


# ===== 测试用例 =====

class TestPubMedParser:
    """PubMed esearch + esummary 两步解析"""

    def test_pubmed_with_fetcher(self):
        """使用 mock fetcher 模拟 esummary 第二步请求"""
        mock_fetcher = lambda url: ESUMMARY_XML
        items = parse(ESEARCH_XML, limit=6, fetcher=mock_fetcher)
        assert len(items) == 2
        assert "Deep Learning" in items[0]["title"]

    def test_pubmed_pmid_extracted(self):
        mock_fetcher = lambda url: ESUMMARY_XML
        items = parse(ESEARCH_XML, limit=6, fetcher=mock_fetcher)
        assert items[0]["meta"]["pmid"] == "39001234"
        assert items[1]["meta"]["pmid"] == "39001235"

    def test_pubmed_url_constructed(self):
        mock_fetcher = lambda url: ESUMMARY_XML
        items = parse(ESEARCH_XML, limit=6, fetcher=mock_fetcher)
        assert items[0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/39001234/"

    def test_pubmed_authors_extracted(self):
        mock_fetcher = lambda url: ESUMMARY_XML
        items = parse(ESEARCH_XML, limit=6, fetcher=mock_fetcher)
        assert "Smith J" in items[0]["meta"]["authors"]

    def test_pubmed_limit_respected(self):
        mock_fetcher = lambda url: ESUMMARY_XML
        items = parse(ESEARCH_XML, limit=1, fetcher=mock_fetcher)
        assert len(items) == 1

    def test_pubmed_no_pmids(self):
        empty_xml = "<eSearchResult><IdList></IdList></eSearchResult>"
        mock_fetcher = lambda url: ESUMMARY_XML
        items = parse(empty_xml, fetcher=mock_fetcher)
        assert items == []

    def test_pubmed_fetch_failure_returns_empty(self):
        """fetcher 抛异常时返回空列表"""
        def failing_fetcher(url):
            raise Exception("network error")
        items = parse(ESEARCH_XML, fetcher=failing_fetcher)
        assert items == []


class TestBioRxivParser:
    """bioRxiv JSON 解析"""

    def test_parse_biorxiv_json(self):
        items = parse(BIORXIV_JSON, limit=6)
        assert len(items) == 2
        assert "RNA-seq" in items[0]["title"]

    def test_biorxiv_doi_extracted(self):
        items = parse(BIORXIV_JSON)
        assert items[0]["meta"]["doi"] == "10.1101/2026.07.10.123456"

    def test_biorxiv_url_constructed(self):
        items = parse(BIORXIV_JSON)
        assert "10.1101/2026.07.10.123456" in items[0]["url"]

    def test_biorxiv_authors_extracted(self):
        items = parse(BIORXIV_JSON)
        assert "Brown A" in items[0]["meta"]["authors"]

    def test_biorxiv_category_extracted(self):
        items = parse(BIORXIV_JSON)
        assert items[0]["meta"]["category"] == "neuroscience"

    def test_biorxiv_empty(self):
        items = parse(BIORXIV_EMPTY)
        assert items == []

    def test_biorxiv_limit_respected(self):
        items = parse(BIORXIV_JSON, limit=1)
        assert len(items) == 1


class TestPubmedParserEdgeCases:
    """边界条件"""

    def test_empty_content(self):
        assert parse("") == []

    def test_invalid_json_as_biorxiv(self):
        items = parse("{invalid json}")
        assert items == []

    def test_invalid_xml_as_pubmed(self):
        items = parse("<not><valid>xml")
        mock_fetcher = lambda url: ""
        # 无 PMID 匹配,应返回空
        items2 = parse("<not><valid>xml", fetcher=mock_fetcher)
        assert items2 == []
