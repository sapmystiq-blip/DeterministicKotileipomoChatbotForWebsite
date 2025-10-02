#!/usr/bin/env python3
"""Generate structured FAQ JSON files from docs/faq_inventory.md."""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = REPO_ROOT / "docs" / "faq_inventory.md"
FAQ_TREE_PATH = REPO_ROOT / "docs" / "faq_tree.json"
FAQ_ENTRIES_PATH = REPO_ROOT / "docs" / "faq_entries.json"
FAQ_META_PATH = REPO_ROOT / "docs" / "faq_meta.json"


@dataclass
class HeadingInfo:
    slug: str
    labels: Dict[str, str]


HEADING_INFO: Dict[str, HeadingInfo] = {
    "1. Tutustu Leipomoon": HeadingInfo(
        slug="tutustu",
        labels={"fi": "Tutustu leipomoon", "en": "Discover the bakery", "sv": "Lär känna bageriet"},
    ),
    "Sijainti & saapuminen": HeadingInfo(
        slug="sijainti-ja-saapuminen",
        labels={"fi": "Sijainti & saapuminen", "en": "Location & arrival", "sv": "Läge & ankomst"},
    ),
    "Aukioloajat": HeadingInfo(
        slug="aukioloajat",
        labels={"fi": "Aukioloajat", "en": "Opening hours", "sv": "Öppettider"},
    ),
    "Myymäläpalvelut": HeadingInfo(
        slug="myymala-palvelut",
        labels={"fi": "Myymäläpalvelut", "en": "In-store services", "sv": "Tjänster i butiken"},
    ),
    "Tarinamme": HeadingInfo(
        slug="tarinamme",
        labels={"fi": "Tarinamme", "en": "Our story", "sv": "Vår berättelse"},
    ),
    "2. Menu": HeadingInfo(
        slug="menu",
        labels={"fi": "Menu", "en": "Menu", "sv": "Meny"},
    ),
    "Uunituoreet": HeadingInfo(
        slug="menu-tuoreet",
        labels={"fi": "Uunituoreet", "en": "Fresh items", "sv": "Färska produkter"},
    ),
    "Valikoiman yleiskuva": HeadingInfo(
        slug="valikoiman-yleiskuva",
        labels={"fi": "Valikoiman yleiskuva", "en": "Overview of the range", "sv": "Översikt av sortimentet"},
    ),
    "Karjalanpiirakat": HeadingInfo(
        slug="karjalanpiirakat",
        labels={"fi": "Karjalanpiirakat", "en": "Karelian pies", "sv": "Karelska piroger"},
    ),
    "Samosat & curry-twistit": HeadingInfo(
        slug="samosat-ja-curry-twistit",
        labels={"fi": "Samosat & curry-twistit", "en": "Samosas & curry twists", "sv": "Samosor & curry-twists"},
    ),
    "Makeat": HeadingInfo(
        slug="makeat",
        labels={"fi": "Makeat", "en": "Sweet treats", "sv": "Sötsaker"},
    ),
    "Pakasteet": HeadingInfo(
        slug="menu-pakasteet",
        labels={"fi": "Pakasteet", "en": "Frozen", "sv": "Frysta produkter"},
    ),
    "Pakasteet & raakapakasteet": HeadingInfo(
        slug="pakasteet-ja-raakapakasteet",
        labels={"fi": "Pakasteet & raakapakasteet", "en": "Frozen & bake-at-home", "sv": "Fryst & färdig att grädda"},
    ),
    "Ainesosat ja ruokavaliot": HeadingInfo(
        slug="ruokavaliot",
        labels={"fi": "Ainesosat ja ruokavaliot", "en": "Dietary needs & ingredients", "sv": "Kostbehov & ingredienser"},
    ),
    "Allergeenilistat": HeadingInfo(
        slug="allergeenilistat",
        labels={"fi": "Allergeenilistat", "en": "Allergen lists", "sv": "Allergenlistor"},
    ),
    "Viljat & gluteeni": HeadingInfo(
        slug="viljat-ja-gluteeni",
        labels={"fi": "Viljat & gluteeni", "en": "Grains & gluten", "sv": "Spannmål & gluten"},
    ),
    "Maito & muna": HeadingInfo(
        slug="maito-ja-muna",
        labels={"fi": "Maito & muna", "en": "Milk & eggs", "sv": "Mjölk & ägg"},
    ),
    "Vegaaniset & maidottomat vaihtoehdot": HeadingInfo(
        slug="vegaaniset-ja-maidottomat",
        labels={"fi": "Vegaaniset & maidottomat", "en": "Vegan & dairy-free", "sv": "Veganska & mjölkfria"},
    ),
    "Muut allergeenit": HeadingInfo(
        slug="muut-allergeenit",
        labels={"fi": "Muut allergeenit", "en": "Other allergens", "sv": "Övriga allergener"},
    ),
    "3. Tuotteet": HeadingInfo(
        slug="tuotteet",
        labels={"fi": "Tuotteet", "en": "Products", "sv": "Produkter"},
    ),
    "4. Tilaus": HeadingInfo(
        slug="tilaus",
        labels={"fi": "Tilaus", "en": "Ordering", "sv": "Beställning"},
    ),
    "Tilaamisen Peruspolku": HeadingInfo(
        slug="tilaamisen-peruspolku",
        labels={"fi": "Tilaamisen peruspolku", "en": "Everyday ordering", "sv": "Beställningsflöde"},
    ),
    "Tilauskanavat": HeadingInfo(
        slug="tilauskanavat",
        labels={"fi": "Tilauskanavat", "en": "Ordering channels", "sv": "Beställningskanaler"},
    ),
    "Tilauksen eteneminen": HeadingInfo(
        slug="tilauksen-eteneminen",
        labels={"fi": "Tilauksen eteneminen", "en": "Order progress", "sv": "Beställningens gång"},
    ),
    "Minimimäärät & saatavuus": HeadingInfo(
        slug="minimimaarat-ja-saatavuus",
        labels={"fi": "Minimimäärät & saatavuus", "en": "Minimums & availability", "sv": "Minimikrav & tillgänglighet"},
    ),
    "Tilauksen muokkaus tai peruutus": HeadingInfo(
        slug="tilauksen-muokkaus",
        labels={"fi": "Tilauksen muokkaus tai peruutus", "en": "Modify or cancel", "sv": "Ändra eller avboka"},
    ),
    "Aikataulut": HeadingInfo(
        slug="aikataulut",
        labels={"fi": "Aikataulut", "en": "Lead times", "sv": "Tidsscheman"},
    ),
    "Suuret & Räätälöidyt Tilaukset": HeadingInfo(
        slug="suuret-ja-rateloidyt",
        labels={"fi": "Suuret & räätälöidyt tilaukset", "en": "Large & custom orders", "sv": "Stora & skräddarsydda beställningar"},
    ),
    "Juhlat & catering": HeadingInfo(
        slug="juhlat-ja-catering",
        labels={"fi": "Juhlat & catering", "en": "Parties & catering", "sv": "Fester & catering"},
    ),
    "Yritys- ja tapahtumatilaukset": HeadingInfo(
        slug="yritys-ja-tapahtumatilaukset",
        labels={"fi": "Yritys- ja tapahtumatilaukset", "en": "Corporate & events", "sv": "Företag & evenemang"},
    ),
    "Kakut & räätälöidyt tuotteet": HeadingInfo(
        slug="kakut-ja-rateloidyt",
        labels={"fi": "Kakut & räätälöidyt tuotteet", "en": "Cakes & custom items", "sv": "Tårtor & specialprodukter"},
    ),
    "Ennakkovaatimukset & sopiminen": HeadingInfo(
        slug="ennakkovaatimukset",
        labels={"fi": "Ennakkovaatimukset & sopiminen", "en": "Prerequisites & agreements", "sv": "Förutsättningar & överenskommelser"},
    ),
    "Nouto & Toimitus": HeadingInfo(
        slug="nouto-ja-toimitus",
        labels={"fi": "Nouto & toimitus", "en": "Pickup & delivery", "sv": "Avhämtning & leverans"},
    ),
    "Noutopaikka & -ajat": HeadingInfo(
        slug="noutopaikka-ja-ajat",
        labels={"fi": "Noutopaikka & -ajat", "en": "Pickup location & times", "sv": "Avhämtningsplats & tider"},
    ),
    "Kuljetusvaihtoehdot": HeadingInfo(
        slug="kuljetusvaihtoehdot",
        labels={"fi": "Kuljetusvaihtoehdot", "en": "Delivery options", "sv": "Leveransalternativ"},
    ),
    "Toimitusalueet & rajoitteet": HeadingInfo(
        slug="toimitusalueet",
        labels={"fi": "Toimitusalueet & rajoitteet", "en": "Delivery areas & limits", "sv": "Leveransområden & begränsningar"},
    ),
    "Kuljetuskustannukset ja ohjeet": HeadingInfo(
        slug="kuljetuskustannukset",
        labels={"fi": "Kuljetuskustannukset ja ohjeet", "en": "Delivery costs & guidance", "sv": "Leveranskostnader & anvisningar"},
    ),
    "5. Maksaminen & Hinnoittelu": HeadingInfo(
        slug="maksaminen",
        labels={"fi": "Maksaminen & hinnoittelu", "en": "Payment & pricing", "sv": "Betalning & prissättning"},
    ),
    "Maksutavat": HeadingInfo(
        slug="maksutavat",
        labels={"fi": "Maksutavat", "en": "Payment methods", "sv": "Betalningssätt"},
    ),
    "Ennakkomaksu & maksulinkit": HeadingInfo(
        slug="ennakkomaksu-ja-maksulinkit",
        labels={"fi": "Ennakkomaksu & maksulinkit", "en": "Advance payment & payment links", "sv": "Förskottsbetalning & betalningslänkar"},
    ),
    "Alennukset & hinnat": HeadingInfo(
        slug="alennukset-ja-hinnat",
        labels={"fi": "Alennukset & hinnat", "en": "Discounts & pricing", "sv": "Rabatter & priser"},
    ),
    "Lahjakortit ja kuitit": HeadingInfo(
        slug="lahjakortit-ja-kuitit",
        labels={"fi": "Lahjakortit ja kuitit", "en": "Gift cards & receipts", "sv": "Presentkort & kvitton"},
    ),
    "6. Kestävyys & Yhteisö": HeadingInfo(
        slug="kestavyys",
        labels={"fi": "Kestävyys & yhteisö", "en": "Sustainability & community", "sv": "Hållbarhet & gemenskap"},
    ),
    "Pakkaukset & ympäristö": HeadingInfo(
        slug="pakkaukset-ja-ymparisto",
        labels={"fi": "Pakkaukset & ympäristö", "en": "Packaging & environment", "sv": "Förpackningar & miljö"},
    ),
    "Hävikki & lahjoitukset": HeadingInfo(
        slug="havikki-ja-lahjoitukset",
        labels={"fi": "Hävikki & lahjoitukset", "en": "Waste & donations", "sv": "Svinn & donationer"},
    ),
    "Yhteistyö & yhteisö": HeadingInfo(
        slug="yhteistyo-ja-yhteiso",
        labels={"fi": "Yhteistyö & yhteisö", "en": "Partnerships & community", "sv": "Samarbeten & gemenskap"},
    ),
    "Palaute & arvostelut": HeadingInfo(
        slug="palaute-ja-arvostelut",
        labels={"fi": "Palaute & arvostelut", "en": "Feedback & reviews", "sv": "Feedback & recensioner"},
    ),
}

FLATTEN_HEADINGS = {
    "Sijainti & saapuminen",
    "Aukioloajat",
    "Myymäläpalvelut",
    "Tarinamme",
    "Valikoiman yleiskuva",
    "Karjalanpiirakat",
    "Samosat & curry-twistit",
    "Makeat",
    "Tilauskanavat",
    "Tilauksen eteneminen",
    "Minimimäärät & saatavuus",
    "Tilauksen muokkaus tai peruutus",
    "Aikataulut",
    "Noutopaikka & -ajat",
    "Kuljetusvaihtoehdot",
    "Toimitusalueet & rajoitteet",
    "Kuljetuskustannukset ja ohjeet",
    "Maksutavat",
    "Ennakkomaksu & maksulinkit",
    "Alennukset & hinnat",
    "Lahjakortit ja kuitit",
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "item"


@dataclass
class TreeNode:
    id: str
    path: List[str]
    labels: Dict[str, str]
    children: Dict[str, "TreeNode"] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "path": self.path,
            "label": self.labels,
            "children": [child.to_dict() for child in self.children.values()],
        }


def build_tree_and_entries() -> Tuple[List[TreeNode], List[dict]]:
    if not INVENTORY_PATH.exists():
        raise SystemExit(f"Inventory file missing: {INVENTORY_PATH}")

    lines = INVENTORY_PATH.read_text(encoding="utf-8").splitlines()
    stack: List[Tuple[int, List[str], str]] = []  # (level, path, heading_text)
    nodes: Dict[Tuple[str, ...], TreeNode] = {}
    root_order: List[Tuple[str, ...]] = []
    entries: List[dict] = []
    seen_ids: defaultdict[str, int] = defaultdict(int)

    def ensure_node(path: List[str], heading_text: str) -> TreeNode:
        key = tuple(path)
        if key in nodes:
            return nodes[key]
        info = HEADING_INFO.get(heading_text)
        if info is None:
            raise ValueError(f"Missing heading mapping for '{heading_text}'")
        node = TreeNode(id=info.slug, path=path.copy(), labels=info.labels.copy())
        nodes[key] = node
        if len(path) == 1:
            root_order.append(key)
        else:
            parent_key = tuple(path[:-1])
            parent = nodes.get(parent_key)
            if parent is None:
                raise ValueError(f"Parent node missing for path {path}")
            parent.children.setdefault(node.id, node)
        return node

    for line in lines:
        heading_match = re.match(r"^(#{2,4})\s+(.*)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            info = HEADING_INFO.get(text)
            if info is None:
                # Skip the document title (# FAQ Inventory)
                if level == 1:
                    continue
                raise ValueError(f"No slug mapping defined for heading '{text}'")
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent_path = stack[-1][1] if stack else []
            if text in FLATTEN_HEADINGS:
                # Keep questions under the parent category without creating a new node
                stack.append((level, parent_path, text))
            else:
                path = parent_path + [info.slug]
                ensure_node(path, text)
                stack.append((level, path, text))
            continue

        if line.strip().startswith("-") and "— source:" in line:
            if not stack:
                raise ValueError(f"Question found outside a category: '{line}'")
            current_path = stack[-1][1]
            question_part, source_part = line.split("— source:", 1)
            question = question_part[2:].strip()
            sources = [src.strip() for src in source_part.split(",")]
            base_id = slugify(question)
            seen_ids[base_id] += 1
            q_id = base_id if seen_ids[base_id] == 1 else f"{base_id}-{seen_ids[base_id]}"
            entries.append({
                "id": q_id,
                "question": {"fi": question},
                "category_path": current_path,
                "sources": sources,
            })
            continue

        # Skip notes or empty lines silently

    roots = [nodes[key] for key in root_order]
    return roots, entries


def main() -> None:
    roots, entries = build_tree_and_entries()
    faq_tree = [node.to_dict() for node in roots]
    version = datetime.now(timezone.utc).isoformat(timespec="seconds")
    FAQ_TREE_PATH.write_text(json.dumps(faq_tree, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    FAQ_ENTRIES_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    FAQ_META_PATH.write_text(
        json.dumps({"faq_version": version}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "Wrote "
        f"{FAQ_TREE_PATH.relative_to(REPO_ROOT)}, "
        f"{FAQ_ENTRIES_PATH.relative_to(REPO_ROOT)} and "
        f"{FAQ_META_PATH.relative_to(REPO_ROOT)}"
    )


if __name__ == "__main__":
    main()
