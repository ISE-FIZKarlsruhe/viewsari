"""Rewrite oa:hasBodyValue literals into oa:hasBody pointing to oa:TextualBody resources.

Usage: python rewrite_hasbodyvalue.py <input.ttl> <output.ttl>

Each `oa:hasBodyValue "X"` triple on subject `vkb:S` becomes:
    `oa:hasBody vkb:body_<S> .`
with a paired block emitted at the bottom of the file:
    vkb:body_<S> a oa:TextualBody ;
        rdf:value "X" ;
        dc:format "text/plain" ;
        dc:language "en" .

Subject → body IRI mapping:
  vkb:annotation_NNN          -> vkb:body_NNN
  ..._m_...                   -> ..._b_...   (single substitution of _m_ → _b_)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RDF_PREFIX_LINE = "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"

HAS_BODY_RE = re.compile(
    r'^(?P<indent>\s*)oa:hasBodyValue\s+(?P<lit>"(?:[^"\\]|\\.)*")\s*(?P<term>[;.])\s*$'
)
SUBJECT_RE = re.compile(r'^(?P<subj>[A-Za-z][A-Za-z0-9_-]*:[A-Za-z0-9_.\-]+)\b')


def derive_body_iri(subject: str) -> str:
    if not subject.startswith("vkb:"):
        raise ValueError(f"Unexpected subject namespace: {subject}")
    local = subject[len("vkb:") :]
    if local.startswith("annotation_"):
        return "vkb:body_" + local[len("annotation_") :]
    if "_m_" in local:
        return "vkb:" + local.replace("_m_", "_b_", 1)
    return "vkb:body_" + local


def rewrite(input_path: Path, output_path: Path) -> tuple[int, int]:
    bodies: list[tuple[str, str]] = []
    out_lines: list[str] = []
    current_subject: str | None = None
    rdf_prefix_inserted = False
    last_prefix_idx = -1
    replaced = 0

    with input_path.open("r", encoding="utf-8") as fin:
        for line in fin:
            if line.startswith("@prefix "):
                out_lines.append(line)
                last_prefix_idx = len(out_lines) - 1
                if line.startswith("@prefix rdf:"):
                    rdf_prefix_inserted = True
                continue

            stripped = line.lstrip()
            if stripped and not stripped[0].isspace() and not stripped.startswith("#"):
                m_subj = SUBJECT_RE.match(line)
                if m_subj:
                    current_subject = m_subj.group("subj")

            m_body = HAS_BODY_RE.match(line)
            if m_body and current_subject is not None:
                body_iri = derive_body_iri(current_subject)
                literal = m_body.group("lit")
                indent = m_body.group("indent")
                term = m_body.group("term")
                bodies.append((body_iri, literal))
                out_lines.append(f"{indent}oa:hasBody {body_iri} {term}\n")
                replaced += 1
            else:
                out_lines.append(line)

    if not rdf_prefix_inserted:
        out_lines.insert(last_prefix_idx + 1, RDF_PREFIX_LINE)

    with output_path.open("w", encoding="utf-8") as fout:
        fout.writelines(out_lines)
        fout.write("\n# --- TextualBody resources (rdf:value carries the surface form) ---\n\n")
        for body_iri, literal in bodies:
            fout.write(
                f"{body_iri} a oa:TextualBody ;\n"
                f"    rdf:value {literal} ;\n"
                f"    dc:format \"text/plain\" ;\n"
                f"    dc:language \"en\" .\n\n"
            )

    return replaced, len(bodies)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: rewrite_hasbodyvalue.py <input.ttl> <output.ttl>", file=sys.stderr)
        sys.exit(1)
    inp, outp = Path(sys.argv[1]), Path(sys.argv[2])
    r, b = rewrite(inp, outp)
    print(f"{inp.name}: replaced {r} oa:hasBodyValue triples, wrote {b} TextualBody blocks")