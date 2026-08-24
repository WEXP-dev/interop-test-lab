"""Service routing for interoperability intake.

These are NON-NORMATIVE SERVICE ROUTES. They decide who does the work and in
what order. They are not WEXP Profiles, not Claim Classes, not Boundary Classes,
and not verdicts. Nothing here changes what any evidence supports.

A submitter describes their situation. They do not choose their route: a
submitter's own classification is an input, never an authority. The rubric below
is public so anyone can see how they will be routed, and it is applied on the
WEXP side either way.

Order matters, and it is privacy first. A case that needs private material is
routed for review BEFORE that material is sent anywhere, which is the only
ordering that actually protects it.
"""

from __future__ import annotations

SELF_SERVICE = "SELF_SERVICE"
ASSISTED_REVIEW = "ASSISTED_REVIEW"
JOINT_RESEARCH = "JOINT_RESEARCH"

ROUTES = (SELF_SERVICE, ASSISTED_REVIEW, JOINT_RESEARCH)

EXTERNAL_WORDING = {
    SELF_SERVICE: "Run it automatically.",
    ASSISTED_REVIEW: "Review it with us.",
    JOINT_RESEARCH: "Research it with us.",
}


def route(case: dict) -> dict:
    """Return the service route for one intake, with the reason that decided it.

    `case` uses only facts a newcomer can supply. No Claim Class, no Boundary
    Class, no Evaluation Profile, no envelope vocabulary appears here.
    """
    reasons = []

    # 1. Privacy first. Anything needing non-public material is reviewed before
    #    that material moves, not after.
    if case.get("requires_private_material") or case.get("special_disclosure_conditions"):
        return {
            "route": ASSISTED_REVIEW,
            "reason": "the case needs material that must not be sent to a public intake, "
                      "so it is reviewed before anything private is shared",
            "external_wording": EXTERNAL_WORDING[ASSISTED_REVIEW],
        }

    # 2. Is the semantic mapping itself the question? If nobody has established
    #    how this evidence maps to a WEXP claim, that is research, and running it
    #    automatically would answer a question nobody has asked properly yet.
    if case.get("semantic_mapping_is_the_question") or not case.get("existing_mapping_known", False):
        reasons.append("no established mapping from this evidence to a bounded WEXP claim")
        return {
            "route": JOINT_RESEARCH,
            "reason": "; ".join(reasons),
            "external_wording": EXTERNAL_WORDING[JOINT_RESEARCH],
        }

    # 3. Known class, public material, and every operational condition already
    #    satisfied. Only then is the automatic path appropriate.
    operational = {
        "public_source": case.get("public_source", False),
        "exact_revision": case.get("exact_revision", False),
        # Supplying an exact revision is not the same as that revision being
        # admitted. The baseline admits exact commits, not repositories, so a
        # known repository at an unadmitted commit is reviewed rather than run.
        "source_identity_admitted": case.get("source_identity_admitted", False),
        "self_contained": case.get("self_contained", False),
        "public_example_material": case.get("public_example_material", False),
    }
    unmet = sorted(k for k, v in operational.items() if not v)
    if not unmet:
        return {
            "route": SELF_SERVICE,
            "reason": "known evidence class, public source at an exact revision that is "
                      "explicitly admitted, self-contained, with public example material",
            "external_wording": EXTERNAL_WORDING[SELF_SERVICE],
        }

    # 4. Known semantics, something operational in the way. Reviewed, never
    #    silently promoted to research: an unusual operating condition is not a
    #    new scientific question.
    return {
        "route": ASSISTED_REVIEW,
        "reason": "known semantics with unmet operational conditions: " + ", ".join(unmet),
        "external_wording": EXTERNAL_WORDING[ASSISTED_REVIEW],
    }
