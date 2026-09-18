"""Scrapes all Bellhaven communities from the website."""
import re
import requests
from bs4 import BeautifulSoup
from config import WEBSITE_BASE, CARE_TYPE_MAP


def _get(path: str) -> BeautifulSoup:
    r = requests.get(WEBSITE_BASE + path, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def _parse_address(dd_tag) -> dict:
    """Parse '<street><br>city, state zip' address block."""
    raw = dd_tag.decode_contents()
    parts = re.split(r"<br\s*/?>", raw, flags=re.IGNORECASE)
    street = BeautifulSoup(parts[0], "html.parser").get_text(strip=True)
    city = state = zip_code = ""
    if len(parts) > 1:
        line2 = BeautifulSoup(parts[1], "html.parser").get_text(strip=True)
        # "Maplewood, OH 44280"
        m = re.match(r"^(.+),\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$", line2)
        if m:
            city, state, zip_code = m.group(1), m.group(2), m.group(3)
        else:
            # fallback: try to split on comma
            comma = line2.rfind(",")
            if comma != -1:
                city = line2[:comma].strip()
                rest = line2[comma + 1:].strip().split()
                state = rest[0] if rest else ""
                zip_code = rest[1] if len(rest) > 1 else ""
    return {"street": street, "city": city, "state": state, "zip": zip_code}


def _scrape_detail(slug: str) -> dict:
    """Fetch a community detail page and return full data."""
    soup = _get(f"/communities/{slug}")
    name = soup.find("h1").get_text(strip=True)
    dl = soup.find("dl", class_="detail")
    data = {"name": name, "slug": slug, "street": "", "city": "", "state": "", "zip": "", "care_types": []}
    if not dl:
        return data
    dts = dl.find_all("dt")
    dds = dl.find_all("dd")
    for dt, dd in zip(dts, dds):
        label = dt.get_text(strip=True).lower()
        if label == "address":
            data.update(_parse_address(dd))
        elif label == "care offerings":
            raw_types = [b.get_text(strip=True) for b in dd.find_all("span", class_="badge")]
            data["care_types"] = raw_types
    return data


def _get_slugs_from_page(page: int) -> list[str]:
    soup = _get(f"/communities?page={page}")
    return [a["href"].split("/communities/")[1]
            for a in soup.select(".card h3 a")
            if "/communities/" in a.get("href", "")]


def scrape_communities() -> list[dict]:
    """Return all Bellhaven communities with full address and care type data."""
    slugs = []
    page = 1
    while True:
        page_slugs = _get_slugs_from_page(page)
        if not page_slugs:
            break
        slugs.extend(page_slugs)
        # Check if there's a next page
        soup = _get(f"/communities?page={page}")
        if not soup.find("a", string=lambda t: t and "Next" in t):
            break
        page += 1

    communities = []
    for slug in slugs:
        detail = _scrape_detail(slug)
        # Normalize care types to CRM values
        detail["care_types_crm"] = [
            CARE_TYPE_MAP.get(ct, ct) for ct in detail["care_types"]
        ]
        # Primary CRM care type (first listed)
        detail["care_type_crm"] = detail["care_types_crm"][0] if detail["care_types_crm"] else ""
        communities.append(detail)
        print(f"  scraped: {detail['name']} ({detail['city']}, {detail['state']})")

    print(f"\nTotal communities scraped: {len(communities)}")
    return communities


if __name__ == "__main__":
    results = scrape_communities()
    for r in results:
        print(r)
