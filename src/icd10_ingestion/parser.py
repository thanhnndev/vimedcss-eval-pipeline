import re
import logging
from typing import List, Dict, Any, Literal, Optional, Set

from bs4 import BeautifulSoup

logger = logging.getLogger("icd10_ingestion.parser")


class ParsedNode:
    """Represents a single parsed node from the ICD-10 HTML tree."""

    def __init__(
        self,
        code: str,
        level: Literal["chapter", "section", "type", "disease"],
        label: str,
        parent_code: Optional[str],
        chapter_code: str,
        chapter_label: str,
    ):
        self.code = code
        self.level = level
        self.label = label
        self.parent_code = parent_code
        self.chapter_code = chapter_code
        self.chapter_label = chapter_label

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "level": self.level,
            "label": self.label,
            "parent_code": self.parent_code,
            "chapter_code": self.chapter_code,
            "chapter_label": self.chapter_label,
        }


class ICD10Parser:
    """Parses KCB ICD-10 API HTML responses into structured ParsedNode lists."""

    def parse_response(self, response_data: Dict[str, Any], language: str) -> List[ParsedNode]:
        """Parse an API response dict into a list of ParsedNode objects.

        Args:
            response_data: The JSON-decoded API response containing "status" and "html".
            language: "en" or "vi" (used for logging).

        Returns:
            List of ParsedNode objects for all chapter/section/type/disease nodes.
        """
        if response_data.get("status") != "success":
            logger.warning(
                f"[parser/{language}] API status is not 'success'; skipping. "
                f"Response: {response_data}"
            )
            return []

        html_str = response_data.get("html", "")
        if not html_str:
            logger.warning(f"[parser/{language}] Empty HTML payload; skipping.")
            return []

        soup = BeautifulSoup(html_str, "html.parser")
        return self._walk_tree(soup, language)

    def _walk_tree(self, soup: BeautifulSoup, language: str) -> List[ParsedNode]:
        """Walk the <ul>/<li> tree depth-first, tracking chapter/section/type context."""
        nodes: List[ParsedNode] = []
        walked_uls: Set[int] = set()  # Track visited <ul> elements by id to avoid double-walk

        current_chapter_code = ""
        current_chapter_label = ""
        current_section_code: Optional[str] = None
        current_section_label = ""
        current_type_code: Optional[str] = None
        current_type_label = ""

        def walk(ul: Any) -> None:
            nonlocal current_chapter_code, current_chapter_label
            nonlocal current_section_code, current_section_label
            nonlocal current_type_code, current_type_label

            ul_id = id(ul)
            if ul_id in walked_uls:
                return
            walked_uls.add(ul_id)

            for li in ul.find_all("li", class_=True, recursive=False):
                classes = li.get("class", [])
                node_type = classes[0] if classes else None

                if node_type not in ("chapter", "section", "type", "disease"):
                    continue

                a_tag = li.find("a")
                if not a_tag:
                    continue

                code_span = a_tag.find("span", class_="code")
                label_span = a_tag.find("span", class_="label")

                if not code_span or not label_span:
                    continue

                code = code_span.get_text(strip=True)
                label_raw = label_span.get_text(strip=True)
                label = self._strip_highline(label_raw)

                if node_type == "chapter":
                    current_chapter_code = code
                    current_chapter_label = label
                    current_section_code = None
                    current_section_label = ""
                    current_type_code = None
                    current_type_label = ""
                    nodes.append(
                        ParsedNode(
                            code=code,
                            level="chapter",
                            label=label,
                            parent_code=None,
                            chapter_code=code,
                            chapter_label=label,
                        )
                    )

                elif node_type == "section":
                    current_section_code = code
                    current_section_label = label
                    current_type_code = None
                    current_type_label = ""
                    nodes.append(
                        ParsedNode(
                            code=code,
                            level="section",
                            label=label,
                            parent_code=None,
                            chapter_code=current_chapter_code,
                            chapter_label=current_chapter_label,
                        )
                    )

                elif node_type == "type":
                    current_type_code = code
                    current_type_label = label
                    nodes.append(
                        ParsedNode(
                            code=code,
                            level="type",
                            label=label,
                            parent_code=current_section_code,
                            chapter_code=current_chapter_code,
                            chapter_label=current_chapter_label,
                        )
                    )

                elif node_type == "disease":
                    nodes.append(
                        ParsedNode(
                            code=code,
                            level="disease",
                            label=label,
                            parent_code=current_type_code,
                            chapter_code=current_chapter_code,
                            chapter_label=current_chapter_label,
                        )
                    )

                # Recurse into nested <ul> within this <li> only
                nested_ul = li.find("ul")
                if nested_ul:
                    walk(nested_ul)

        # Find top-level <ul>
        root_ul = soup.find("ul")
        if root_ul:
            walk(root_ul)
        else:
            # No <ul> wrapper — <li> elements may be direct children of <body> or the document root.
            # Walk any <ul> found under <body>
            body = soup.find("body")
            if body:
                for ul in body.find_all("ul", recursive=False):
                    walk(ul)
            if not nodes:
                # <li> elements are direct children of the document root.
                # Find all top-level <li class="chapter|section|type|disease"> and walk them.
                top_lis = [c for c in soup.children if getattr(c, "name", None) == "li"]
                if top_lis:
                    # Create a synthetic parent for each top-level <li> so walk() can process its children
                    for li in top_lis:
                        # Create a synthetic <ul> wrapper around this <li>
                        wrapper = soup.new_tag("ul")
                        li.wrap(wrapper)
                    # Now find the <ul> that wraps them
                    for ul in soup.find_all("ul"):
                        if id(ul) not in walked_uls:
                            walk(ul)
                            if nodes:
                                break

        return nodes

    @staticmethod
    def _strip_highline(text: str) -> str:
        """Remove <b class="highline"> markup from label text."""
        return re.sub(r"<b class=\"highline\">", "", text).replace("</b>", "")
