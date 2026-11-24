"""2024 presidential primary results from the states' own election offices (DA-6), while the FEC's 2024 Federal Elections
workbook is unpublished.

Each state's official file (certified canvass where one was found) is cached in data/raw/state_primary/<ST>/<date>/
with a manifest of its URL; SOURCES lists them. Files were located and fetched on 2026-11-24 with the project's
User-Agent; nothing behind a bot check was fetched. Two large files are stored gzipped (Pennsylvania's precinct returns,
Arkansas's full data file). State public records: not covered by the project's licence (LICENSE-DATA.md).

States not here, and why (BLOCKED, NO_STATE_CONTEST): their 2024 rows come from Wikipedia (primary_results_wiki.py).

parse() returns one row per state, party and ballot line: the line's name as the state prints it, votes, and the
line's kind (candidate, uncommitted, other: write-ins, no preference, none of the names, blanks where the state
counts them as a line). Statewide totals are summed from counties, districts or precincts where the file has no
statewide row (named in each parser).

Run:  python src/collect/primary_results_states.py      (prints the parsed totals; primary_results.py writes them)
"""
import gzip
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW, fetch, latest  # noqa: E402

RAW_SRC = RAW / "state_primary"
CIVERA = "https://{st}.elstats.civera.com/api/download_contest/{id}_table.csv?split_party=false"


def src(name, url, scratch=None, note=None, party=None):
    return {"name": name, "url": url, "scratch": scratch or name, **({"note": note} if note else {}),
            **({"party": party} if party else {})}


SOURCES = {
    "AL": [src("AL_REP_official_2024_primary_amended.xlsx", "https://www.sos.alabama.gov/sites/default/files/election-2024/RepublicanPartyOfficial-2024PrimaryResult-Amended.xlsx",
               note="certified by the party, amended 2024-04-12 (supersedes the 2024-03-14 file)"),
           src("AL_DEM_official_2024_primary.xlsx", "https://www.sos.alabama.gov/sites/default/files/election-2024/Democratic_Party-Official_2024_Primary_Election_Results.xlsx",
               note="certified by the party 2024-03-14")],
    "AR": [src("AR_2024_preferential_primary_FullDataFile.json.gz", "https://results.tally-enr.com/results/arkansas/1845/FullDataFile.json",
               scratch="AR_2024_preferential_primary_FullDataFile.json", note="stored gzipped"),
           src("AR_2024_preferential_primary_GetElectionInfo.json", "https://enr-results-api.totalresults.com/Election/GetElectionInfo?cId=arkansas&electionID=1845",
               note="isOfficial: true")],
    "CA": [src("CA_25_presidential_by_county.xlsx", "https://elections.cdn.sos.ca.gov/sov/2024-primary/sov/25-presidential-formatted.xlsx",
               note="Statement of Vote; certified 2024-04-12"),
           src("CA_sov_certificate.pdf", "https://elections.cdn.sos.ca.gov/sov/2024-primary/sov/25-sov-certificate.pdf")],
    "CO": [src("CO_REP_pres_2024_contest25994.csv", CIVERA.format(st="co", id=25994), note="SOS historical database; cites the 2023-2024 Abstract of Votes Cast"),
           src("CO_DEM_pres_2024_contest25993.csv", CIVERA.format(st="co", id=25993))],
    "CT": [src("CT_REP_pres_2024_contest35850.csv", CIVERA.format(st="ct", id=35850), note="SOS historical database"),
           src("CT_DEM_pres_2024_contest35851.csv", CIVERA.format(st="ct", id=35851))],
    "DE": [src("DE_20240402_PublicNotice_PresidentialPrimary.pdf", "https://elections.delaware.gov/voter/pdfs/20240402_PublicNotice_DelawarePresidentialPrimaryElection.pdf",
               note="both parties' primaries cancelled")],
    "FL": [src("FL_20240319_ResultsExtract_official.txt", "https://results.elections.myflorida.com/ResultsExtract.Asp?ElectionDate=3/19/2024&OfficialResults=Y&PartyRaces=Y&DataMode=&FormsButton2=Download",
               note="official results extract; race PRE (PPC repeats it by congressional district)")],
    "GA": [src("GA_2024MarPPP_TotalVotesResults.xlsx", "https://results.sos.ga.gov/cdn/results/09378a07-e6cf-4f66-be7c-ca4aa534f99a/Total%20Votes%20Results_332ef1c8-3b90-4708-973e-8af417d6112a.xlsx"),
           src("GA_2024MarPPP_election_api.json", "https://results.sos.ga.gov/results/public/api/elections/Georgia/2024MarPPP", note="isOfficialResults: true")],
    "IL": [src("IL_GP2024Tot.xlsx", "https://www.elections.il.gov/ElectionOperations/DownloadVoteTotals.aspx",
               note="GP2024Tot.xlsx, reached by the page's postback (ddlCurrent=2024); the download link is tokenised"),
           src("IL_2024GPOfficialVote.pdf", "https://www.elections.il.gov/ElectionOperations/DownloadVoteTotals.aspx", note="2024GPOfficialVote.pdf, the official canvass, same postback")],
    "IN": [src("IN_2024Primary_OffCatC_1012_USPresident.json", "https://enr.indianavoters.in.gov/archive/2024Primary/data/OffCatC_1012_B.json"),
           src("IN_2024Primary_settings.json", "https://enr.indianavoters.in.gov/archive/2024Primary/data/settings.json", note="Certified: T")],
    "KS": [src("KS_2024_PPP_Official_Vote_Totals.pdf", "https://sos.ks.gov/elections/24elec/2024-Presidential-Preference-Primary-Official-Vote-Totals.pdf")],
    "KY": [src("KY_2024_Primary_Results.pdf", "https://elect.ky.gov/results/2020-2029/Documents/2024%20Primary%20Results.pdf", note="official certification")],
    "LA": [src("LA_20240323_election_results.xlsx", "https://s3-us-west-2.amazonaws.com/mediaresults.sos.la.gov/HumanReadableElectionResults/20240323/Election+Results+(03-23-2024).xlsx")],
    "MA": [src("MA_REP_electionstats_160659.csv", "https://electionstats.state.ma.us/elections/download/160659/precincts_include:0/", note="certified results database"),
           src("MA_DEM_electionstats_160657.csv", "https://electionstats.state.ma.us/elections/download/160657/precincts_include:0/")],
    "MD": [src("MD_PP24_CongressionalBreakDownRepublican.csv", "https://elections.maryland.gov/elections/archive/2024/election_data/PP24_CongressionalBreakDownRepublican.csv", note="official results"),
           src("MD_PP24_CongressionalBreakDownDemocratic.csv", "https://elections.maryland.gov/elections/archive/2024/election_data/PP24_CongressionalBreakDownDemocratic.csv")],
    "ME": [src("ME_REP_presidential_primary_2024-03-05.xlsx", "https://www1.maine.gov/sos/sites/maine.gov.sos/files/content/assets/REP-20Presidential-20Primary-203.5.2024.xlsx",
               note="from www1.maine.gov; www.maine.gov refuses scripted requests"),
           src("ME_DEM_presidential_primary_2024-03-05.xlsx", "https://www1.maine.gov/sos/sites/maine.gov.sos/files/content/assets/DEM-20Presidential-20Primary-203.5.2024.xlsx",
               note="from www1.maine.gov; www.maine.gov refuses scripted requests")],
    "MI": [src("MI_mvic_GetCountyVoteRecords_696_2024PPR.html", "https://mvic.sos.state.mi.us/VoteHistory/GetCountyVoteRecords?electionId=696",
               note="'PRESIDENTIAL PRIMARY, OFFICIAL', updated 2024-03-19")],
    "MN": [src("MN_20240305_pnpstatewide.txt", "https://electionresultsfiles.sos.mn.gov/20240305/pnpstatewide.txt", note="Last-Modified 2024-03-11; canvassed 2024-03-12")],
    "MO": [src("MO_DEM_party_results_by_county_CD.xlsx", "https://docs.google.com/spreadsheets/d/1OqhDxZjZxap2ZSznd3ELC6KfCzZKO-VncHrJgWyKNaA/export?format=xlsx",
               note="Missouri Democratic Party's final results (a party-run primary), linked from its 2024-03-26 release")],
    "MS": [src("MS_Statewide_Republican_Results24.pdf", "https://www.sos.ms.gov/elections/electionResults/Statewide%20Republican%20Results24.pdf", note="official recapitulation"),
           src("MS_Statewide_Democratic_Recap24.pdf", "https://www.sos.ms.gov/elections/electionResults/Statewide%20Democratic%20Recap24.pdf")],
    "MT": [src("MT_2024_Primary_State_Canvass.pdf", "https://sosmt.gov/wp-content/uploads/wpfd/preview_files/2024-Primary-State-Canvass(b50cfaddb2a87cff54f3cb6a4df8a621).pdf",
               note="state canvass; direct file link (sosmt.gov pages show a browser check)")],
    "NC": [src("results_pct_20240305.zip", "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2024_03_05/results_pct_20240305.zip", note="precinct file dated 2024-04-01, after the canvass")],
    "NE": [src("NE_2024_Primary_Canvass_Book.pdf", "https://sos.nebraska.gov/sites/default/files/doc/elections/2024/2024%20Primary%20Canvass%20Book.pdf", note="Board of State Canvassers official report")],
    "NJ": [src("NJ_2024_official_primary_results_president.pdf", "https://www.nj.gov/state/elections/assets/pdf/election-results/2024/2024-official-primary-results-president.pdf",
               note="INCOMPLETE: lists named candidates only, no uncommitted or write-in lines, so shares are of the named candidates' votes")],
    "NM": [src("NM_REP_president_contest_14424.csv", "https://nm.elstats.civera.com/api/download_contest/14424_table.csv?split_party=false", note="SOS results database; state canvass certified 2024-06-25"),
           src("NM_DEM_president_contest_14425.csv", "https://nm.elstats.civera.com/api/download_contest/14425_table.csv?split_party=false")],
    "OK": [src("2024-ppp-cd-results.pdf", "https://oklahoma.gov/content/dam/ok/en/elections/candidate-filing-archives/2024-candidate-filing-archives/2024-ppp-cd-results.pdf",
               note="official results by congressional district, 2024-03-21")],
    "OR": [src("2024-primary-bluebook.pdf", "https://sos.oregon.gov/blue-book/government/Documents/2024-primary.pdf",
               note="Oregon Blue Book, citing the SOS abstract of votes (the abstract itself returned 404)")],
    "PA": [src("electionreturns_2024_primary_precinctreturns.txt.gz", "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/bulk-data/electionreturns_2024_primary_precinctreturns.txt",
               scratch="electionreturns_2024_primary_precinctreturns.txt", note="stored gzipped; extracted 2024-07-23. INCOMPLETE: no write-in lines, so shares are of the named candidates' votes"),
           src("electionreturns_2024_primary_readme.txt", "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/bulk-data/electionreturns_2024_primary_readme.txt")],
    "PR": [src("PRESIDENTE_Resumen.xml", "https://democrata2024.ceepur.org/ESCRUTINIO_117/data/PRESIDENTE_Resumen.xml",
               note="Democratic party-run primary counted by the CEE; general canvass")],
    "RI": [src("statewide.json", "https://rigov.s3.amazonaws.com/election/results/2024/presidential_preference_primary/statewide.json")],
    "SC": [src("sc_119816_v330796_summary.json", "https://www.enr-scvotes.org/SC/119816/330796/json/en/summary.json", note="Republican primary, final version after certification", party="R"),
           src("sc_119283_v327921_summary.json", "https://www.enr-scvotes.org/SC/119283/327921/json/en/summary.json", note="Democratic primary, final version", party="D")],
    "SD": [src("2024PrimaryStateCanvass_Cert.pdf", "https://sdsos.gov/elections-voting/assets/Archive/2024%20Assets/2024PrimaryStateCanvass&Cert.pdf", note="certified state canvass")],
    "UT": [src("2024-Presidential-Primary-Election-State-Canvass-Signed.pdf", "https://vote.utah.gov/wp-content/uploads/2024/03/2024-Presidential-Primary-Election-State-Canvass-Signed.pdf")],
    "VA": [src("va_contest_160926_table.csv", CIVERA.format(st="va2", id=160926), party="R"),
           src("va_contest_160927_table.csv", CIVERA.format(st="va2", id=160927), party="D")],
    "VT": [src("vt_contest_160916_table.csv", CIVERA.format(st="vt2", id=160916), party="R"),
           src("vt_contest_160915_table.csv", CIVERA.format(st="vt2", id=160915), party="D")],
    "WA": [src("20240312_AllState.csv", "https://results.vote.wa.gov/results/20240312/export/20240312_AllState.csv", note="post-certification export")],
    "WI": [src("County_by_County_Report_all_contests.pdf", "https://elections.wi.gov/sites/default/files/documents/County%20by%20County%20Report_all%20contests.pdf", note="canvass report")],
    "WV": [src("wv_120641_v345534_summary.json", "https://results.enr.clarityelections.com/WV/120641/345534/json/en/summary.json", note="final version, 2024-08-26")],
}
# Official sources that refuse scripted requests (checked 2026-11-24; bot checks are never bypassed). The URL is where
# the official file is, for a download by hand into the same folder layout.
BLOCKED = {
    ("AZ", "both"): ("https://apps.azsos.gov/election/2024/ppe_canvass/2024_PPE_Official_Canvass_20240404.pdf", "Cloudflare challenge"),
    ("DC", "D"): ("https://electionresults.dcboe.org/Downloads/Reports/June_4_2024_Primary_Election_Certified_Results.pdf", "Cloudflare challenge"),
    ("NH", "both"): ("https://www.sos.nh.gov/", "Akamai 'Access Denied'"),
    ("NV", "both"): ("https://www.nvsos.gov/", "Incapsula challenge (the Republican state-run primary allocated no delegates)"),
    ("NY", "both"): ("https://results.elections.ny.gov/", "Cloudflare challenge"),
    ("OH", "both"): ("https://www.ohiosos.gov/globalassets/elections/2024/pri/official/summary-level-results-primary-2024---republican.xlsx", "security-check page on every path"),
    ("TN", "both"): ("https://sos-prod.tnsosgovfiles.com/s3fs-public/document/20240305RepublicanPPPStatewide.pdf", "CloudFront 'Request blocked'"),
    ("TX", "both"): ("https://results.texas-election.com/races", "Cloudflare challenge"),
}
# Contests with no state-run primary to read
NO_STATE_CONTEST = {
    ("DE", "R"): "cancelled (Trump unopposed after Haley withdrew)", ("DE", "D"): "cancelled (Biden the only candidate)",
    ("SD", "R"): "cancelled (Trump unopposed)", ("FL", "D"): "cancelled (Biden the only candidate)",
    ("AK", "R"): "party-run", ("AK", "D"): "party-run", ("DC", "R"): "party-run", ("PR", "R"): "party-run",
    ("ND", "R"): "caucus", ("ND", "D"): "party-run", ("UT", "R"): "caucus", ("MO", "R"): "caucus", ("IA", "R"): "caucus",
    ("IA", "D"): "party-run (mail-in)", ("ID", "R"): "caucus", ("WY", "R"): "caucus", ("HI", "R"): "caucus",
}


def path(st, name):
    try:
        return latest(f"state_primary/{st}", name)
    except FileNotFoundError:
        f = next(x for x in SOURCES[st] if x["name"] == name)
        if f["name"].endswith(".gz") or "postback" in f.get("note", ""):
            raise
        return fetch(f"state_primary/{st}", name, f["url"])


def read_text(st, name, enc="utf-8"):
    p = path(st, name)
    b = gzip.open(p).read() if p.suffix == ".gz" else p.read_bytes()
    return b.decode(enc, errors="replace")


def pdf_text(st, name):
    import fitz
    with fitz.open(path(st, name)) as d:
        return "\n".join(pg.get_text() for pg in d)


def toint(x):
    x = str(x).replace(",", "").strip()
    return int(float(x)) if re.fullmatch(r"-?\d+(\.0+)?", x) else None


def line_kind(name):
    n = str(name).lower()
    if "uncommit" in n or "uninstructed" in n or "noncommit" in n:
        return "uncommitted"
    if re.search(r"write|scatter|no preference|none of|blank|other|miscellaneous|no comprometido", n):
        return "other"
    return "candidate"


SUFFIX = re.compile(r"^(jr|sr|ii|iii|iv)\.?$", re.I)


def clean_name(n):
    """'BIDEN JR., JOSEPH R.' / 'Haley, Nikki R.' -> first names first; all-capitals -> title case."""
    n = re.sub(r"\s+", " ", str(n)).strip()
    n = re.sub(r"^[\"']+([^\"']+)[\"']+\s", r"\1 ", n)               # '"Ron" DeSantis' -> 'Ron DeSantis'
    n = re.sub(r"\s[\"']+[^\"']+[\"']+\s", " ", n)                   # 'Armando "Mando" Perez-Serrato'
    parts = [p.strip() for p in n.split(",")]
    if len(parts) >= 2 and parts[1] and not SUFFIX.match(parts[1]):
        rest = [p for p in parts[2:] if p]
        n = " ".join([parts[1], parts[0]] + rest)
    if n.isupper():
        n = " ".join(w if SUFFIX.match(w) is None else w.title() for w in n.title().split())
        n = re.sub(r"\bDesantis\b", "DeSantis", n)
    return n


def rows(st, party, pairs, note=None):
    return [{"state": st, "party": party, "candidate_name": clean_name(n), "votes": int(v),
             "line": line_kind(n), "parse_note": note} for n, v in pairs]


# ---------------- parsers: each returns a list of rows ----------------
NOT_LINE = re.compile(r"^(total votes cast|total ballots cast|undervotes|overvotes|same day registration|"
                      r"total|blanks?)\b", re.I)


def civera(st, name, party):
    """ElectionStats (CO, CT, NM, VA, VT): candidate header row, party row, a 'State' row with statewide totals."""
    t = pd.read_csv(io.StringIO(read_text(st, name)), header=None, dtype=str)
    hdr = t.iloc[0]
    state = t[t[0].astype(str).str.strip() == "State"].iloc[0]
    pairs = [(hdr[j], toint(state[j])) for j in range(2, len(hdr)) if isinstance(hdr[j], str)
             and not NOT_LINE.search(hdr[j].strip())]
    return rows(st, party, [(n, v) for n, v in pairs if v is not None])


def clarity(st, name, titles):
    out = []
    for c in json.loads(read_text(st, name)):
        party = titles.get(c["C"].strip())
        if party:
            names = [re.sub(r"\s*-\s*WITHDREW$", "", re.sub(r"^(REP|DEM|MTN)\s+", "", n)) for n in c["CH"]]
            out += rows(st, party, zip(names, c["V"]))
    return out


def p_AL():
    t = pd.read_excel(path("AL", "AL_REP_official_2024_primary_amended.xlsx"), sheet_name="Summary", header=None)
    i = t.index[t[0].astype(str).str.strip() == "President"][0]
    pairs = []
    for j in range(i + 1, len(t)):
        n = str(t.iat[j, 0]).strip()
        if n in ("nan", "") or n.lower() == "total":
            break
        pairs.append((n, toint(t.iat[j, 1])))
    out = rows("AL", "R", pairs)
    d = pd.read_excel(path("AL", "AL_DEM_official_2024_primary.xlsx"), header=None)
    end = next(j for j in range(2, d.shape[1]) if isinstance(d.iat[0, j], str))   # next contest's first column
    cnt = d[d[0].notna() & ~d[0].astype(str).str.contains("total", case=False)]
    cnt = cnt.iloc[1:] if str(cnt.iat[0, 0]).strip() in ("nan", "") else cnt
    out += rows("AL", "D", [(d.iat[1, j], pd.to_numeric(cnt.iloc[:, j], errors="coerce").sum()) for j in range(1, end)],
                note="summed over counties")
    return out


def p_AR():
    d = json.loads(read_text("AR", "AR_2024_preferential_primary_FullDataFile.json.gz"))
    out = []
    for c in d["ContestData"]:
        party = {"U.S. President - REP": "R", "U.S. President - DEM": "D"}.get(c["ContestName"].strip())
        if party:
            out += rows("AR", party, [(x["Name"], x["TotalVotes"]) for x in c["Candidates"]])
    return out


def p_CA():
    t = pd.read_excel(path("CA", "CA_25_presidential_by_county.xlsx"), header=None)
    tot = t[t[0].astype(str).str.contains("State Total", case=False)].iloc[0]
    out = []
    for j in range(1, t.shape[1]):
        n, p = t.iat[0, j], str(t.iat[1, j])
        party = "D" if p.startswith("DEM") else "R" if p.startswith("REP") else None
        if party and isinstance(n, str) and toint(tot[j]) is not None:
            out += rows("CA", party, [(n.replace("*", ""), toint(tot[j]))])
    return out


def p_FL():
    t = pd.read_csv(io.StringIO(read_text("FL", "FL_20240319_ResultsExtract_official.txt", "latin-1")), sep="\t", dtype=str)
    t = t[t.RaceCode == "PRE"].copy()
    t["name"] = (t.CanNameFirst.fillna("") + " " + t.CanNameLast.fillna("")).str.strip()
    t["v"] = pd.to_numeric(t.CanVotes)
    s = t.groupby(["PartyCode", "name"], sort=False).v.sum()
    return [r for (p, n), v in s.items() for r in rows("FL", {"REP": "R", "DEM": "D"}[p], [(n, v)], note="summed over counties")]


def p_GA():
    t = pd.read_excel(path("GA", "GA_2024MarPPP_TotalVotesResults.xlsx"), sheet_name="Total Votes")
    out = []
    for office, party in (("President of the US - Rep", "R"), ("President of the US - Dem", "D")):
        x = t[(t["Office Name"].astype(str).str.strip() == office) & t["Choice ID"].notna()
              & ~t["Ballot Name"].astype(str).str.contains(r"^Total", case=False)]
        out += rows("GA", party, zip(x["Ballot Name"].str.replace(r"\s*\(I\)$", "", regex=True), x["Total"]))
    return out


def p_IL():
    t = pd.read_excel(path("IL", "IL_GP2024Tot.xlsx"))
    t = t[t.OfficeName.astype(str).str.strip() == "PRESIDENT"]
    return [r for _, x in t.iterrows() for r in rows("IL", {"REP": "R", "DEM": "D"}[x.PartyAbbrev],
                                                     [(f"{x.CanFirstName} {x.CanLastName}", x.Votes)])]


def p_IN():
    d = json.loads(read_text("IN", "IN_2024Primary_OffCatC_1012_USPresident.json"))
    race = d["Root"]["StatewideSummary"]["Race"]
    race = race if isinstance(race, dict) else race[0]
    return [r for c in race["Candidates"]["Candidate"] if c["PARTY"] in ("R", "D")
            for r in rows("IN", c["PARTY"], [(c["NAME_ON_BALLOT"], c["TOTAL"])])]


def p_KS():
    txt = pdf_text("KS", "KS_2024_PPP_Official_Vote_Totals.pdf")
    out = []
    for m in re.finditer(r"^([DR])-(.+?)\s*\n([\d,]+)\n", txt, re.M):
        out += rows("KS", m.group(1), [(m.group(2), toint(m.group(3)))])
    return out


def p_KY():
    """By county with a 'Total Votes' row; the candidate order is the header's (first and last names on two lines)."""
    txt = pdf_text("KY", "KY_2024_Primary_Results.pdf")
    out = []
    for party, word in (("R", "Republican Party"), ("D", "Democratic Party")):
        i = txt.index(f"President of the United States\n{word}")
        block = txt[i:txt.index("Total Votes", i)]
        head = block.split("\n", 2)[2]
        head = head[:re.search(r"\n(Adair)\n", head).start()]
        tot = re.match(r"Total Votes\n((?:[\d,]+\n)+)", txt[txt.index("Total Votes", i):]).group(1).split()
        names = [re.sub(r"\s+", " ", n).replace('"', "").strip() for n in names_ky(head)]
        if len(names) != len(tot):
            raise ValueError(f"KY {party}: {len(names)} names, {len(tot)} totals")
        out += rows("KY", party, zip(names, map(toint, tot)))
    return out


def names_ky(head):
    """'Donald J.\\nTRUMP\\nNikki R.\\nHALEY "UNCOMMITTE\\nD"\\nRon\\nDeSANTIS...' -> names. A surname is the
    all-caps (or DeSANTIS) line; the uncommitted line is quoted and may be split across lines."""
    h = head.replace('"UNCOMMITTE\nD"', '\n"UNCOMMITTED"\n')
    toks = [x.strip() for x in h.split("\n") if x.strip()]
    out, first = [], []
    for x in toks:
        if x.startswith('"'):
            out.append(x.strip('"').title())
        elif re.fullmatch(r"(De)?[A-Z][A-Z.'\- ]+(JR\.)?", x):
            out.append(" ".join(first + [x.title()]))
            first = []
        else:
            first.append(x)
    return out


def p_LA():
    t = pd.read_excel(path("LA", "LA_20240323_election_results.xlsx"), sheet_name="Multi-Parish(Parish)", header=None)
    out = []
    for party, word in (("D", "Democratic"), ("R", "Republican")):
        i = t.index[t[0].astype(str).str.contains(f"Presidential Nominee -- {word}", na=False)][0]
        hdr = t.iloc[i + 1]
        j = next(k for k in range(i + 2, len(t)) if str(t.iat[k, 0]).strip().lower().startswith("total"))
        out += rows("LA", party, [(re.sub(r"\s*\((DEM|REP)\)$", "", hdr[c]), toint(t.iat[j, c]))
                                  for c in range(1, t.shape[1]) if isinstance(hdr[c], str) and toint(t.iat[j, c]) is not None])
    return out


def p_MA():
    out = []
    for name, party in (("MA_REP_electionstats_160659.csv", "R"), ("MA_DEM_electionstats_160657.csv", "D")):
        t = pd.read_csv(io.StringIO(read_text("MA", name)), dtype=str)
        tot = t[t.iloc[:, 0].astype(str).str.upper().str.startswith("TOTAL")].iloc[0]
        out += rows("MA", party, [(c, toint(tot[c])) for c in t.columns[3:] if not NOT_LINE.search(c.strip())
                                  or c.strip().lower() == "blanks"])
    return out


def p_MD():
    out = []
    for name, party in (("MD_PP24_CongressionalBreakDownRepublican.csv", "R"), ("MD_PP24_CongressionalBreakDownDemocratic.csv", "D")):
        t = pd.read_csv(io.StringIO(read_text("MD", name)), dtype=str)
        t.columns = [c.strip() for c in t.columns]
        t = t[t["Office District"].isna() & (t["Office Name"].str.strip() == "President - Vice Pres")]   # statewide
        cds = [c for c in t.columns if c.startswith("Congressional District")]
        t["v"] = t[cds].apply(pd.to_numeric, errors="coerce").sum(axis=1)
        out += rows("MD", party, zip(t["Candidate Name"], t.v), note="summed over congressional districts")
    return out


def p_ME():
    out = []
    for name, party in (("ME_REP_presidential_primary_2024-03-05.xlsx", "R"), ("ME_DEM_presidential_primary_2024-03-05.xlsx", "D")):
        x = pd.ExcelFile(path("ME", name))
        t = pd.read_excel(x, sheet_name=next(n for n in x.sheet_names if n.upper() == "SUMMARY"), header=None)
        tot = t[t.astype(str).apply(lambda c: c.str.contains("STATEWIDE TOTALS")).any(axis=1)].iloc[0]
        hdr = t.iloc[1]
        out += rows("ME", party, [(hdr[c], toint(tot[c])) for c in t.columns if isinstance(hdr[c], str)
                                  and "TOTAL" not in hdr[c].upper()])
    return out


def p_MI():
    h = read_text("MI", "MI_mvic_GetCountyVoteRecords_696_2024PPR.html")
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", h))
    block = txt[txt.index("PRESIDENT OF THE UNITED STATES"):txt.index("Total Votes:")]
    out = []
    for m in re.finditer(r"(DEMOCRATIC|REPUBLICAN) \| \| ([^|]+?) \| \| ([\d,]+) \|", block):
        out += rows("MI", m.group(1)[0], [(m.group(2), toint(m.group(3)))])
    return out


def p_MN():
    out = []
    for line in read_text("MN", "MN_20240305_pnpstatewide.txt").splitlines():
        f = line.split(";")
        if len(f) > 13 and "Presidential" in f[4] and f[10] in ("R", "DFL"):
            out += rows("MN", "R" if f[10] == "R" else "D", [(f[7], toint(f[13]))])
    return out


def p_MO():
    """Missouri Democrats' party-run primary: the statewide row of the county sheet."""
    x = pd.ExcelFile(path("MO", "MO_DEM_party_results_by_county_CD.xlsx"))
    for sh in x.sheet_names:
        t = pd.read_excel(x, sheet_name=sh, header=None)
        hit = t.index[t.astype(str).apply(lambda c: c.str.contains("statewide|state total|total", case=False)).any(axis=1)]
        hdr_i = next((i for i in range(6) if t.iloc[i].astype(str).str.contains("Biden", case=False).any()), None)
        if hdr_i is None or not len(hit):
            continue
        tot = t.loc[hit[-1]]
        hdr = t.iloc[hdr_i]
        pairs = [(hdr[c], toint(tot[c])) for c in t.columns if isinstance(hdr[c], str) and toint(tot[c]) is not None
                 and not re.search(r"county|district|total|turnout|delegate", hdr[c], re.I)]
        if pairs:
            return rows("MO", "D", [(re.sub(r"\s*votes?$", "", n, flags=re.I), v) for n, v in pairs],
                        note=f"party-run; sheet {sh!r}")
    raise ValueError("no statewide row found")


def blocks_sum(txt, start_pat, stop_pat, party_word):
    """Name/party/number sequences (MS): after each candidate name and its party word, the numbers until the next name
    are that candidate's county votes; summed over every page's block."""
    sums = {}
    for m in re.finditer(start_pat, txt):
        seg = txt[m.end():]
        stop = re.search(stop_pat, seg)
        seg = seg[:stop.start()] if stop else seg
        toks = [t.strip() for t in seg.split("\n") if t.strip()]
        cur = None
        for i, t in enumerate(toks):
            if i + 1 < len(toks) and toks[i + 1] == party_word and not re.fullmatch(r"[\d,X]+", t):
                cur = t
            elif cur and re.fullmatch(r"[\d,]+", t):
                sums.setdefault(cur, []).append(toint(t))
    # the last page carries each candidate's statewide total: where the largest number equals the sum of the rest,
    # it is that total
    return {k: (max(v) if 2 * max(v) == sum(v) else sum(v)) for k, v in sums.items()}


def p_MS():
    r = blocks_sum(pdf_text("MS", "MS_Statewide_Republican_Results24.pdf"), r"United States-President\n", r"United States-Senate",
                   "Republican")
    d = blocks_sum(pdf_text("MS", "MS_Statewide_Democratic_Recap24.pdf"), r"United States-President\n", r"United States-Senate",
                   "Democrat") or blocks_sum(pdf_text("MS", "MS_Statewide_Democratic_Recap24.pdf"), r"United States-President\n",
                                             r"United States-Senate", "Democratic")
    return rows("MS", "R", r.items()) + rows("MS", "D", d.items())


def p_MT():
    """Per party: two names, then county pairs; the last pair is the Total."""
    txt = pdf_text("MT", "MT_2024_Primary_State_Canvass.pdf")
    out = []
    for party, word in (("D", "Democratic"), ("R", "Republican")):
        i = txt.index(f"PRESIDENT {word}\n")
        seg = txt[i:].split("\n")[1:]
        names, nums = [], []
        for t in seg:
            t = t.strip()
            if re.fullmatch(r"\d+", t):
                nums.append(int(t))
            elif nums:
                break
            elif t:
                names.append(t)
        names = [" ".join(names[k:k + 2]) for k in range(0, len(names), 2)]
        k = len(names)
        if len(nums) % k:
            raise ValueError(f"MT {party}: {len(nums)} numbers for {k} names")
        out += rows("MT", party, zip(names, nums[-k:]))
    return out


def p_NC():
    z = zipfile.ZipFile(path("NC", "results_pct_20240305.zip"))
    t = pd.read_csv(z.open(z.namelist()[0]), sep="\t", dtype=str, encoding="latin-1")
    out = []
    for party in ("REP", "DEM"):
        x = t[t["Contest Name"].str.strip() == f"PRESIDENTIAL PREFERENCE ({party})"].copy()
        s = pd.to_numeric(x["Total Votes"]).groupby(x.Choice, sort=False).sum()
        out += rows("NC", party[0], s.items(), note="summed over precincts")
    return out


def p_NE():
    txt = pdf_text("NE", "NE_2024_Primary_Canvass_Book.pdf")
    i = [m.start() for m in re.finditer(r"President of the United States", txt)][2]
    seg = txt[i:i + 30000]
    out = []
    for party, word in (("R", "Republican Party Nomination"), ("D", "Democratic Party Nomination")):
        j = seg.index(word)
        # names: two lines each (first names, surname); totals: the numbers after 'Total' up to the first county
        head = [x.strip() for x in seg[seg.index("County", j) + len("County"):seg.index("Total", j)].split("\n")
                if x.strip()]
        tot = []
        for x in seg[seg.index("Total", j) + 5:].split("\n"):
            if x.strip():
                if toint(x) is None:
                    break
                tot.append(toint(x))
        if len(head) != 2 * len(tot):
            raise ValueError(f"NE {party}: {len(head)} name lines for {len(tot)} totals")
        out += rows("NE", party, zip([f"{head[k]} {head[k + 1]}" for k in range(0, len(head), 2)], tot))
    return out


def p_NJ():
    """A page per candidate: name (after 'Address'), party, county lines, then the candidate's 'Total'."""
    txt = pdf_text("NJ", "NJ_2024_official_primary_results_president.pdf")
    out = []
    for m in re.finditer(r"Address\n(.+?)\n.*?\n(Democratic|Republican)\n.*?\nTotal\n([\d,]+)\n", txt, re.S):
        out += rows("NJ", m.group(2)[0], [(re.sub(r"\s*\(w\)|\s*\*", "", m.group(1)).strip(), toint(m.group(3)))])
    return out


def p_NM():
    return civera("NM", "NM_REP_president_contest_14424.csv", "R") + civera("NM", "NM_DEM_president_contest_14425.csv", "D")


def p_OK():
    txt = pdf_text("OK", "2024-ppp-cd-results.pdf")
    out = {}
    for m in re.finditer(r"FOR PRESIDENT\n(Republican|Democrat\w*)\n", txt):
        party = m.group(1)[0]
        seg = txt[m.end():]
        stop = re.search(r"FOR PRESIDENT|Page \d+ of", seg)
        seg = seg[:stop.start()] if stop else seg
        for c in re.finditer(r"\n([A-Z][A-Z.'\" \-]+[A-Za-z.]*)\n(\d[\d,]*)\n(\d[\d,]*)\n(\d[\d,]*)\n(\d[\d,]*)\n[\d.]+%", "\n" + seg):
            v = [toint(c.group(k)) for k in range(2, 6)]
            out[(party, c.group(1).strip())] = out.get((party, c.group(1).strip()), 0) + max(v)
    return [r for (p, n), v in out.items() for r in rows("OK", p, [(n, v)], note="summed over congressional districts")]


def p_OR():
    txt = pdf_text("OR", "2024-primary-bluebook.pdf")
    seg = txt[txt.index("United States President"):txt.index("United States Representative")]
    out, party = [], None
    toks = [t.strip() for t in seg.split("\n") if t.strip()][1:]
    for i, t in enumerate(toks):
        if t in ("Democrat", "Republican"):
            party = t[0]
        elif party and i + 1 < len(toks) and toint(toks[i + 1]) is not None and toint(t) is None and t != "Total":
            n = t.replace("*", "")
            n = " ".join(reversed([x.strip() for x in n.split(",", 1)])) if "," in n else n
            out += rows("OR", party, [(n, toint(toks[i + 1]))])
    return out


def p_PA():
    cols = ["year", "type", "county", "precinct", "office_rank", "district", "party_rank", "ballot_pos", "office", "party",
            "cand_no", "last", "first", "middle", "suffix", "votes"]
    t = pd.read_csv(io.StringIO(read_text("PA", "electionreturns_2024_primary_precinctreturns.txt.gz", "latin-1")),
                    header=None, usecols=range(16), names=cols, dtype=str)
    t = t[t.office.str.strip() == "USP"].copy()
    t["name"] = (t["first"].fillna("") + " " + t["last"].fillna("")).str.strip().str.title()
    s = pd.to_numeric(t.votes).groupby([t.party.str.strip(), t.name], sort=False).sum()
    return [r for (p, n), v in s.items() if p in ("REP", "DEM") for r in rows("PA", p[0], [(n, v)], note="summed over precincts")]


def p_PR():
    import xml.etree.ElementTree as ET
    root = ET.fromstring(path("PR", "PRESIDENTE_Resumen.xml").read_bytes())
    return rows("PR", "D", [(o.findtext("name/en"), toint(o.findtext("votes"))) for o in root.iter("option")
                            if toint(o.findtext("votes")) is not None], note="party-run, counted by the CEE")


def p_RI():
    d = json.loads(read_text("RI", "statewide.json"))
    out = []
    for c in d["contests"]:
        m = re.match(r"(DEM|REP) Presidential", c["name"])
        if m:
            out += rows("RI", m.group(1)[0], [(x["name"], toint(x["votes"])) for x in c["candidates"]])
    return out


def p_SD():
    """Democratic only (the Republican contest was cancelled). The names head the first page, two lines each (a
    hyphenated surname runs onto a third); the 'Total' row follows the last county."""
    txt = pdf_text("SD", "2024PrimaryStateCanvass_Cert.pdf")
    i = txt.index("Presidential Candidate")
    start = txt.rfind("\n\n", 0, txt.index("\nAurora\n", txt.rfind("SEAL", 0, i)))
    head = txt[start:txt.index("\nAurora\n", start)]
    toks = [x.strip() for x in head.split("\n") if x.strip()]
    joined = []
    for t in toks:
        if joined and joined[-1].endswith("-"):
            joined[-1] += t
        else:
            joined.append(t)
    names = [re.sub(r"\s+", " ", " ".join(joined[k:k + 2])) for k in range(0, len(joined), 2)]
    tot = re.search(r"\nTotal\n((?:[\d,]+\n){%d})" % len(names), txt[i:]).group(1).split()
    return rows("SD", "D", zip(names, map(toint, tot)))


def p_UT():
    """Democratic only (Utah Republicans caucused): names after 'U.S. PRESIDENT', totals after 'Total Votes Cast Per
    Candidate'."""
    txt = pdf_text("UT", "2024-Presidential-Primary-Election-State-Canvass-Signed.pdf")
    i = txt.index("U.S. PRESIDENT\n") + len("U.S. PRESIDENT\n")
    names = [x.strip() for x in txt[i:txt.index("Beaver County", i)].split("\n") if x.strip()]
    j = txt.index("Total Votes Cast Per Candidate\n", i) + len("Total Votes Cast Per Candidate\n")
    tot = [x.strip() for x in txt[j:].split("\n") if x.strip()][:len(names)]
    return rows("UT", "D", zip(names, map(toint, tot)))


def p_WA():
    t = pd.read_csv(io.StringIO(read_text("WA", "20240312_AllState.csv")), dtype=str)
    out = []
    for race, party in (("President - Republican Party", "R"), ("President - Democratic Party", "D")):
        x = t[t.Race.str.strip() == race]
        out += rows("WA", party, zip(x.Candidate, pd.to_numeric(x.Votes)))
    return out


def p_WI():
    """'Office Totals:' line per party block; candidate names from the block header."""
    txt = pdf_text("WI", "County_by_County_Report_all_contests.pdf")
    out = []
    for party in ("REP", "DEM"):
        for m in re.finditer(rf"Total Votes Cast\n((?:{party}\n)+)", txt):
            k = m.group(1).count("\n")
            seg = txt[m.end():]
            names, part = [], ""
            toks = seg.split("\n")
            j = 0
            while len(names) < k:
                t = toks[j]
                if t.strip() and not re.fullmatch(r"[\d,]+", t.strip()):
                    if t.endswith(" "):
                        part += t                     # a name line ending in a space continues on the next line
                    else:
                        names.append((part + t).strip())
                        part = ""
                j += 1
            ot = seg.index("Office Totals:")
            if re.search(r"Total Votes Cast\n", seg[:ot]):
                continue                     # not the last page of this block
            rest = [x.strip() for x in toks[j:] if x.strip()]
            if rest and rest[0] == "SCATTERING":     # a column with no party heading
                names.append("SCATTERING")
            nums = seg[ot:].split("\n")[1:len(names) + 2]
            out += rows("WI", party[0], zip(names, map(toint, nums[1:])))
            break
    return out


def p_CO():
    return civera("CO", "CO_REP_pres_2024_contest25994.csv", "R") + civera("CO", "CO_DEM_pres_2024_contest25993.csv", "D")


def p_CT():
    return civera("CT", "CT_REP_pres_2024_contest35850.csv", "R") + civera("CT", "CT_DEM_pres_2024_contest35851.csv", "D")


def p_VA():
    return civera("VA", "va_contest_160926_table.csv", "R") + civera("VA", "va_contest_160927_table.csv", "D")


def p_VT():
    return civera("VT", "vt_contest_160916_table.csv", "R") + civera("VT", "vt_contest_160915_table.csv", "D")


def p_SC():
    return clarity("SC", "sc_119816_v330796_summary.json", {"REP President": "R"}) + \
        clarity("SC", "sc_119283_v327921_summary.json", {"DEM President": "D", "President": "D"})


def p_WV():
    return clarity("WV", "wv_120641_v345534_summary.json", {"PRESIDENT - REP": "R", "PRESIDENT - DEM": "D"})


def source_for(st, party):
    """The state's file for that party: the one whose name says the party, else the first."""
    pat = {"R": r"REP|Republican|_R_", "D": r"DEM|Democratic|_D_"}[party]
    fs = SOURCES[st]
    if any("party" in f for f in fs):
        return next(f for f in fs if f.get("party") == party)
    named = [f for f in fs if re.search(pat, f["name"])]
    if named:
        return named[0]
    other = {"R": r"DEM|Democratic", "D": r"REP|Republican"}[party]
    return next((f for f in fs if not re.search(other, f["name"])), fs[0])


def parse(states=None):
    out, errors = [], {}
    for st in states or [s for s in SOURCES if s != "DE"]:   # Delaware's file is the cancellation notice
        try:
            got = globals()[f"p_{st}"]()
            for r in got:
                f = source_for(st, r["party"])
                r["source_file"], r["source_url"], r["source_note"] = f["name"], f["url"], f.get("note")
            out += got
        except Exception as e:  # noqa: BLE001
            errors[st] = f"{type(e).__name__}: {str(e)[:300]}"
    return pd.DataFrame(out), errors


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 200)
    r, errors = parse(sys.argv[1:] or None)
    if len(r):
        print(r.groupby(["state", "party"]).agg(lines=("votes", "size"), votes=("votes", "sum"),
                                               top=("candidate_name", "first")).to_string())
    for st, e in errors.items():
        print("ERROR", st, e)
    return r


if __name__ == "__main__":
    main()
