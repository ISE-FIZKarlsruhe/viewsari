import json
from pathlib import Path
from collections import defaultdict

if __name__ == "__main__":
    GT_DIR = Path("/Users/sro/Desktop/viewsari/obliquer/data/viewsari/ground_truth")

    ORDER = [
        ("Giotto di Bondone", "Giotto", "giotto_enriched.json"),
        ("Giovanni Cimabue", "Cimabue", "cimabue_enriched.json"),
        ("Pietro Cavallini", "Cavallini", "cavallini_enriched.json"),
        ("Filippo Brunelleschi", "Brunelleschi", "brunelleschi_enriched.json"),
        ("Leon Battista Alberti", "Alberti", "alberti_enriched.json"),
        ("Alesso Baldovinetti", "Baldovinetti", "baldovinetti_enriched.json"),
        ("Gherardo di Giovanni", "Gherardo", "gherardo_enriched.json"),
        ("Domenico Ghirlandaio", "Ghirlandaio", "ghirlandaio_enriched.json"),
        ("Antonio and Piero Pollaiuolo", "Pollaiuolo", "pollaiuolo_enriched.json"),
        ("Andrea del Verrocchio", "Verrocchio", "verrocchio_enriched.json"),
        ("Sandro Botticelli", "Botticelli", "botticelli_enriched.json"),
        ("Cosimo Rosselli", "Rosselli", "rosselli_enriched.json"),
        ("Filippino Lippi", "Lippi", "lippi_enriched.json"),
        ("Jacopo da Pontormo", "Pontormo", "pontormo_enriched.json"),
        ("Michelangelo Buonarroti", "Buonarroti", "michelangelo_enriched.json"),
        ("Tiziano da Cadore (Titian)", "Titian", "titian_enriched.json"),
    ]

    BRUN_GT = {175,176,177,178,179,180,183,184,189,194,199,200,202,203,206,210}
    MICH_GT = set(range(27, 76))

    def find_file(fname):
        for sub in ["1","2","3","4","7","9"]:
            p = GT_DIR / sub / fname
            if p.exists():
                return p
        return None

    # Per-biography stats
    rows_all = []
    rows_artwork = []
    overall_types = {"explicit artwork mention":0,"implicit artwork mention":0,"coreferent":0,"generic mention":0}

    # Cross-biography entity tracking
    qid_to_bios = defaultdict(set)        # wikidata_id -> set of biographies
    ookb_to_bios = defaultdict(set)       # ookb_uri -> set of biographies
    clusters_unlinked = 0  # entity_id clusters with no wd and no ookb
    clusters_total_per_bio_sum = 0

    # headless / chain stats
    chain_lengths_non_singleton = []
    singleton_count = 0
    non_singleton_count = 0
    empty_paragraph_count = 0
    total_paragraphs_iter = 0
    coref_resolved = 0
    coref_total = 0
    coref_truly_headless = 0  # both entity_id and refers_to are null

    LONGEST = (0, "", None)

    for full, short, fname in ORDER:
        fp = find_file(fname); assert fp
        data = json.loads(fp.read_text())
        if "brunelleschi" in fname:
            paras = [p for p in data if p["paragraph_id"] in BRUN_GT]
        elif "michelangelo" in fname:
            paras = [p for p in data if p["paragraph_id"] in MICH_GT]
        else:
            paras = data
        n_para = len(paras)
        exp=imp=cor=gen=0
        clusters = {}  # eid -> list of mentions

        for p in paras:
            ms = p.get("mentions",[])
            if len(ms) == 0:
                empty_paragraph_count += 1
            total_paragraphs_iter += 1
            for m in ms:
                t = m.get("type","")
                if t == "explicit artwork mention": exp += 1
                elif t == "implicit artwork mention": imp += 1
                elif t == "coreferent":
                    cor += 1
                    coref_total += 1
                    if m.get("refers_to") is not None or m.get("entity_id") is not None:
                        coref_resolved += 1
                    if m.get("refers_to") is None and m.get("entity_id") is None:
                        coref_truly_headless += 1
                elif t == "generic mention": gen += 1
                overall_types[t] = overall_types.get(t,0)+1
                eid = m.get("entity_id")
                if eid:
                    clusters.setdefault(eid, []).append(m)

        ment = exp+imp+cor+gen
        art_ment = exp+imp
        n_ent = len(clusters)
        linked = ookb = unlinked = 0
        import re as _re
        for eid, ms in clusters.items():
            cqid = None; cfrag = None
            for m in ms:
                wid = m.get("wikidata_id") or ""
                if isinstance(wid, list): wid = wid[0] if wid else ""
                if isinstance(wid, str) and wid.startswith("http"):
                    mq = _re.search(r"(Q\d+)$", wid.rstrip("/"))
                    if mq: cqid = mq.group(1); break
            if not cqid:
                for m in ms:
                    if m.get("ookb") and m.get("ookb_uri"):
                        o = m.get("ookb_uri")
                        if isinstance(o, list): o = o[0] if o else ""
                        if isinstance(o, str) and "#" in o:
                            cfrag = o.rsplit("#",1)[-1]; break
            if cqid:
                linked += 1
                qid_to_bios[cqid].add(short)
            elif cfrag:
                ookb += 1
                ookb_to_bios[cfrag].add(short)
            else:
                unlinked += 1
                clusters_unlinked += 1
            # chain stats
            if len(ms) == 1:
                singleton_count += 1
            else:
                non_singleton_count += 1
                chain_lengths_non_singleton.append(len(ms))
                if len(ms) > LONGEST[0]:
                    LONGEST = (len(ms), short, eid)
        clusters_total_per_bio_sum += n_ent

        rows_all.append((short, n_para, exp, imp, cor, gen, ment, n_ent, linked, ookb))
        rows_artwork.append((short, n_para, exp, imp, art_ment, n_ent, linked, ookb))

    # Totals row
    T_para = sum(r[1] for r in rows_all)
    T_exp  = sum(r[2] for r in rows_all)
    T_imp  = sum(r[3] for r in rows_all)
    T_cor  = sum(r[4] for r in rows_all)
    T_gen  = sum(r[5] for r in rows_all)
    T_ment = sum(r[6] for r in rows_all)
    T_ent  = sum(r[7] for r in rows_all)
    T_lnk  = sum(r[8] for r in rows_all)
    T_ook  = sum(r[9] for r in rows_all)

    print("=== Table 3.1 (all mentions) ===")
    print(f"{'Bio':14s} {'Pars':>4s} {'Exp':>4s} {'Imp':>4s} {'Cor':>4s} {'Gen':>4s} {'Ment':>5s} {'Ent':>4s} {'Lnk':>4s} {'OOK':>4s}")
    for r in rows_all:
        print(f"{r[0]:14s} {r[1]:4d} {r[2]:4d} {r[3]:4d} {r[4]:4d} {r[5]:4d} {r[6]:5d} {r[7]:4d} {r[8]:4d} {r[9]:4d}")
    print(f"{'TOTAL':14s} {T_para:4d} {T_exp:4d} {T_imp:4d} {T_cor:4d} {T_gen:4d} {T_ment:5d} {T_ent:4d} {T_lnk:4d} {T_ook:4d}")

    print("\n=== Table 3.2 (artwork only) ===")
    T_art_ment = sum(r[4] for r in rows_artwork)
    print(f"{'Bio':14s} {'Pars':>4s} {'Exp':>4s} {'Imp':>4s} {'Art':>4s} {'Ent':>4s} {'Lnk':>4s} {'OOK':>4s}")
    for r in rows_artwork:
        print(f"{r[0]:14s} {r[1]:4d} {r[2]:4d} {r[3]:4d} {r[4]:4d} {r[5]:4d} {r[6]:4d} {r[7]:4d}")
    print(f"{'TOTAL':14s} {T_para:4d} {T_exp:4d} {T_imp:4d} {T_art_ment:4d} {T_ent:4d} {T_lnk:4d} {T_ook:4d}")

    print("\n=== Mention type distribution ===")
    total_m = sum(overall_types.values())
    for k,v in overall_types.items():
        print(f"  {k:35s} {v:6d}  {100*v/total_m:.2f}%")
    print(f"  TOTAL                                 {total_m}")

    print("\n=== Entity stats ===")
    print(f"  Per-biography sum total clusters: {clusters_total_per_bio_sum}")
    print(f"  LINKED total: {T_lnk}")
    print(f"  OOKB total: {T_ook}")
    print(f"  Unlinked clusters (no wd, no ookb): {clusters_unlinked}")
    print(f"  Singletons: {singleton_count}, non-singletons: {non_singleton_count}")
    chain_lengths_non_singleton.sort()
    mean_len = sum(chain_lengths_non_singleton)/len(chain_lengths_non_singleton)
    n = len(chain_lengths_non_singleton)
    median_len = chain_lengths_non_singleton[n//2] if n%2 else (chain_lengths_non_singleton[n//2-1]+chain_lengths_non_singleton[n//2])/2
    print(f"  Mean non-singleton chain length: {mean_len:.2f}")
    print(f"  Median non-singleton chain length: {median_len}")
    print(f"  Longest chain: {LONGEST[0]} ({LONGEST[1]} - {LONGEST[2]})")
    print(f"  Empty paragraphs: {empty_paragraph_count} / {total_paragraphs_iter}  ({100*empty_paragraph_count/total_paragraphs_iter:.1f}%)")
    print(f"  Coref resolved (entity_id OR refers_to): {coref_resolved}/{coref_total}  ({100*coref_resolved/coref_total:.2f}%)")
    print(f"  Truly headless coreferents (BOTH null): {coref_truly_headless}")

    print("\n=== Deduplication breakdown ===")
    shared_qids = sum(1 for q,bios in qid_to_bios.items() if len(bios) > 1)
    extra_qid_entries = sum(len(bios)-1 for q,bios in qid_to_bios.items() if len(bios) > 1)
    shared_ookb = sum(1 for u,bios in ookb_to_bios.items() if len(bios) > 1)
    extra_ookb_entries = sum(len(bios)-1 for u,bios in ookb_to_bios.items() if len(bios) > 1)
    unique_qids = len(qid_to_bios)
    unique_ookbs = len(ookb_to_bios)
    print(f"  Unique Wikidata QIDs across all bios: {unique_qids}")
    print(f"  Unique OOKB IRIs across all bios: {unique_ookbs}")
    print(f"  Shared QIDs (in >=2 bios): {shared_qids}")
    print(f"    extra entries from sharing (sum of k-1): {extra_qid_entries}")
    print(f"  Shared OOKB IRIs (in >=2 bios): {shared_ookb}")
    print(f"    extra entries from sharing (sum of k-1): {extra_ookb_entries}")
    print(f"  Unlinked clusters (no wd, no ookb): {clusters_unlinked}")
    print(f"  Per-bio sum: {clusters_total_per_bio_sum}")
    print(f"  Predicted KG artwork count = unique_qids + unique_ookbs = {unique_qids + unique_ookbs}")
    print(f"  Gap (per-bio - kg) = {clusters_total_per_bio_sum} - {unique_qids + unique_ookbs} = {clusters_total_per_bio_sum - (unique_qids + unique_ookbs)}")
    print(f"  Gap breakdown: extra_qid_entries({extra_qid_entries}) + extra_ookb_entries({extra_ookb_entries}) + unlinked({clusters_unlinked}) = {extra_qid_entries + extra_ookb_entries + clusters_unlinked}")

    # Show longest chain context
    print(f"\n  Longest cluster: {LONGEST}")
