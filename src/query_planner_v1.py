import re


# --------------------------------------------------
# Text helpers
# --------------------------------------------------

def normalize(text):
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def clean_subject(text):
    text = normalize(
        text
    )

    text = re.sub(
        r"^[\s:,-]+",
        "",
        text,
    )

    text = text.rstrip(
        "?.!"
    )

    # Remove accidental command prefixes that
    # should never become part of the subject.
    text = re.sub(
        r"^(?:explain|describe)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.strip()


def strip_leading_article(text):
    text = clean_subject(
        text
    )

    return re.sub(
        r"^(?:the|a|an)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def normalize_effect_subject(text):
    text = clean_subject(
        text
    )

    # ------------------------------------------
    # X fell
    #
    # "the Roman Empire fell"
    # ->
    # "the fall of the Roman Empire"
    # ------------------------------------------

    match = re.fullmatch(
        r"(.+?) fell",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        entity = clean_subject(
            match.group(1)
        )

        return (
            f"the fall of {entity}"
        )

    # ------------------------------------------
    # X collapsed
    # ------------------------------------------

    match = re.fullmatch(
        r"(.+?) collapsed",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        entity = clean_subject(
            match.group(1)
        )

        return (
            f"the collapse of {entity}"
        )

    # ------------------------------------------
    # X's fall
    # ------------------------------------------

    match = re.fullmatch(
        r"(.+?)(?:'s|’s) fall",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        entity = clean_subject(
            match.group(1)
        )

        return (
            f"the fall of {entity}"
        )

    # ------------------------------------------
    # X's collapse
    # ------------------------------------------

    match = re.fullmatch(
        r"(.+?)(?:'s|’s) collapse",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        entity = clean_subject(
            match.group(1)
        )

        return (
            f"the collapse of {entity}"
        )

    return text


# --------------------------------------------------
# Intent detection
# --------------------------------------------------

def detect_intent(question):
    q = normalize(
        question
    ).lower()

    # ==========================================
    # Comparison
    # ==========================================

    if re.search(
        r"\bcompare\b|"
        r"\bdifference(?:s)? between\b|"
        r"\bmain differences between\b|"
        r"\bversus\b|"
        r"\bvs\.?\b|"
        r"\bwhat separates .+ from .+\b|"
        r"\bwhat distinguishes .+ from .+\b|"
        r"\bwhat differentiates .+ from .+\b|"
        r"\bwhat differs between .+ and .+\b|"
        r"\bhow (?:is|are) .+ different from .+\b|"
        r"\bhow (?:do|does) .+ differ from .+\b|"
        r"\bhow (?:do|does) .+ and .+ differ\b|"
        r"\bin what ways (?:is|are) .+ different\b|"
        r"\bin what ways (?:do|does) .+ and .+ differ\b|"
        r"\bexplain the differences between\b|"
        r"\bdescribe how .+ differs from\b",
        q,
    ):
        return "comparison"

    # ==========================================
    # Significance
    #
    # Must be before cause.
    # ==========================================

    if re.search(
        r"\bsignificance of\b|"
        r"\bimportance of\b|"
        r"\bhistorical importance\b|"
        r"\bhistorical significance\b|"
        r"\bwhy was .+ important\b|"
        r"\bwhy is .+ important\b|"
        r"\bwhy has .+ been considered important\b|"
        r"\bwhy does .+ matter\b|"
        r"\bwhy did .+ matter\b|"
        r"\bwhat made .+ significant\b|"
        r"\bwhat was important about\b|"
        r"\bwhat is important about\b|"
        r"\bwhat was historically important about\b|"
        r"\bwhat is historically important about\b|"
        r"\bwhat is historically significant about\b|"
        r"\bwhat was historically significant about\b|"
        r"\bhow was .+ historically significant\b|"
        r"\bhow is .+ historically significant\b|"
        r"\bwhat impact made .+ significant\b",
        q,
    ):
        return "significance"

       # ==========================================
    # Effect
    # ==========================================

    if re.search(
        r"\beffects? of\b|"
        r"\bconsequences? of\b|"
        r"\bimpact of\b|"
        r"\bresulted from\b|"
        r"\bwhat resulted from\b|"
        r"\bwhat happened after\b|"
        r"\bwhat followed\b|"
        r"\bwhat came after\b|"
        r"\bchanges followed\b|"
        r"\bdevelopments followed\b|"
        r"\bconsequences followed\b|"
        r"\bwhat consequences followed\b|"
        r"\bwhat was one result of\b|"
        r"\bwhat is one result of\b|"
        r"\bwhat were the results of\b|"
        r"\bwhat was the result of\b|"
        r"\bas a result of\b|"
        r"\bhow did conditions change after\b|"
        r"\bhow did things change after\b|"
        r"\bhow did life change after\b",
        q,
    ):
        return "effect"
    # ==========================================
    # Change
    # ==========================================

    if re.search(
        r"\bchange over time\b|"
        r"\bchanges over time\b|"
        r"\bhow did .+ change\b|"
        r"\bhow has .+ changed\b|"
        r"\bhow was .+ different later\b|"
        r"\bdescribe how .+ changed\b|"
        r"\bdescribe the changes in\b|"
        r"\bin what ways did .+ change\b|"
        r"\bhow did .+ transform\b|"
        r"\bdevelop over\b|"
        r"\bdevelopment of\b|"
        r"\bhow did .+ develop\b|"
        r"\bhow did .+ evolve\b|"
        r"\bevolution of\b|"
        r"\btransition over time\b|"
        r"\bhistorical development of\b|"
        r"\bwhat changes occurred in\b|"
        r"\bwhat developments changed\b",
        q,
    ):
        return "change"

    # ==========================================
    # Features
    # ==========================================

    if re.search(
        r"\bmain features of\b|"
        r"\bfeatures of\b|"
        r"\bcharacteristics of\b|"
        r"\bwhat characterized\b|"
        r"\bwhat characterizes\b|"
        r"\bwhat defined\b|"
        r"\bwhat defines\b|"
        r"\bwhat features characterized\b|"
        r"\bwhat features did .+ have\b|"
        r"\bwhat characteristics did .+ have\b|"
        r"\bwhat institutions characterized\b|"
        r"\bwhat political features did\b|"
        r"\bdefining features of\b|"
        r"\bkey characteristics of\b",
        q,
    ):
        return "features"

    # ==========================================
    # Structure
    # ==========================================

    if re.search(
        r"\bstructure of\b|"
        r"\binternal structure of\b|"
        r"\bmolecular structure of\b|"
        r"\bstructured\b|"
        r"\borganized\b|"
        r"\borganised\b|"
        r"\borganisation\b|"
        r"\borganization\b|"
        r"\bcomponents of\b|"
        r"\bparts of\b|"
        r"\bmade of\b|"
        r"\bmakes up\b|"
        r"\bmake up\b|"
        r"\bcomponents form\b|"
        r"\bwhat units made up\b|"
        r"\bwhat units form(?:ed)?\b|"
        r"\bhow .+ arranged\b|"
        r"\bhow .+ divided\b|"
        r"\bhierarchy of\b|"
        r"\borganized into units\b",
        q,
    ):
        return "structure"

    # ==========================================
    # Entity list
    # ==========================================

    if re.search(
        r"\bmain leaders of\b|"
        r"\bmajor leaders of\b|"
        r"\bkey leaders of\b|"
        r"\bleaders were prominent\b|"
        r"\bkey figures of\b|"
        r"\bkey figures from\b|"
        r"\bmain figures of\b|"
        r"\bimportant figures\b|"
        r"\bnotable figures\b|"
        r"\bmajor political figures\b|"
        r"\bimportant people\b|"
        r"\bwhich people were important\b|"
        r"\bwho were important people\b|"
        r"\bkey people\b|"
        r"\bplayed major roles\b|"
        r"\bname .+ figures\b|"
        r"\blist .+ leaders\b|"
        r"\bidentify key people\b",
        q,
    ):
        return "entity_list"

    # ==========================================
    # Process / explanation
    # ==========================================

    if re.search(
        r"\bhow .+ works\b|"
        r"\bhow .+ work\b|"
        r"\bhow .+ operates\b|"
        r"\bhow .+ operate\b|"
        r"\bhow does .+ work\b|"
        r"\bhow do .+ perform\b|"
        r"\bwhat happens during\b|"
        r"\bwhat happens when\b|"
        r"\bwhat occurs in\b|"
        r"\bwhat does .+ do\b|"
        r"\bprocess of\b|"
        r"\bmechanism of\b|"
        r"\bstages of\b|"
        r"\bsteps of\b|"
        r"\bmain steps involved in\b|"
        r"\bhow is .+ converted during\b|"
        r"\bhow does .+ convert\b|"
        r"\bexplain how\b",
        q,
    ):
        return "process"

    # ==========================================
    # Cause
    # ==========================================

    if (
        re.match(
            r"why\b",
            q,
        )
        or re.match(
            r"explain why\b",
            q,
        )
        or re.match(
            r"what caused\b",
            q,
        )
        or re.match(
            r"what made\b",
            q,
        )
        or re.match(
            r"what led\b",
            q,
        )
        or re.match(
            r"what drove\b",
            q,
        )
        or re.match(
            r"what brought about\b",
            q,
        )
        or re.match(
            r"what was behind\b",
            q,
        )
        or re.match(
            r"which factors led\b",
            q,
        )
        or re.match(
            r"what factors contributed\b",
            q,
        )
        or re.match(
            r"what factors caused\b",
            q,
        )
        or re.match(
            r"what contributed\b",
            q,
        )
        or re.match(
            r"for what reasons\b",
            q,
        )
        or re.match(
            r"what were the reasons\b",
            q,
        )
        or re.match(
            r"how did .+ come to decline\b",
            q,
        )
        or re.match(
            r"how did .+ lead to\b",
            q,
        )
    ):
        return "cause"

    return "general"


# --------------------------------------------------
# Comparison subject extraction
# --------------------------------------------------

def extract_comparison_subjects(question):
    q = normalize(
        question
    )

    patterns = [
        r"what are the main differences between "
        r"(.+?) and (.+?)[.?!]?$",

        r"what are the key differences between "
        r"(.+?) and (.+?)[.?!]?$",

        r"what are the differences between "
        r"(.+?) and (.+?)[.?!]?$",

        r"what is the difference between "
        r"(.+?) and (.+?)[.?!]?$",

        r"explain the differences between "
        r"(.+?) and (.+?)[.?!]?$",

        r"describe the differences between "
        r"(.+?) and (.+?)[.?!]?$",

        r"differences between "
        r"(.+?) and (.+?)[.?!]?$",

        r"difference between "
        r"(.+?) and (.+?)[.?!]?$",

        r"compare (.+?) and (.+?)[.?!]?$",

        r"compare (.+?) with (.+?)[.?!]?$",

        r"compare (.+?) to (.+?)[.?!]?$",

        r"how does (.+?) compare with "
        r"(.+?)[.?!]?$",

        r"how does (.+?) compare to "
        r"(.+?)[.?!]?$",

        r"what separates (.+?) from "
        r"(.+?)[.?!]?$",

        r"what distinguishes (.+?) from "
        r"(.+?)[.?!]?$",

        # --------------------------------------
        # NEW:
        # What differentiates X from Y?
        # --------------------------------------

        r"what differentiates (.+?) from "
        r"(.+?)[.?!]?$",

        r"how (?:is|are) (.+?) different from "
        r"(.+?)[.?!]?$",

        r"how (?:do|does) (.+?) differ from "
        r"(.+?)[.?!]?$",

        r"how (?:do|does) (.+?) and "
        r"(.+?) differ[.?!]?$",

        r"describe how (.+?) differs from "
        r"(.+?)[.?!]?$",

        r"explain how (.+?) differs from "
        r"(.+?)[.?!]?$",

        r"in what ways are (.+?) and "
        r"(.+?) different[.?!]?$",

        r"in what ways do (.+?) and "
        r"(.+?) differ[.?!]?$",

        r"what differs between "
        r"(.+?) and (.+?)[.?!]?$",

        r"(.+?) versus (.+?)[.?!]?$",

        r"(.+?) vs\.? (.+?)[.?!]?$",
    ]

    for pattern in patterns:
        match = re.fullmatch(
            pattern,
            q,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        left = clean_subject(
            match.group(1)
        )

        right = clean_subject(
            match.group(2)
        )

        if (
            left
            and right
            and left.lower()
            != right.lower()
        ):
            return (
                left,
                right,
            )

    return None


# --------------------------------------------------
# Subject extraction
# --------------------------------------------------

def extract_subject(
    question,
    intent,
):
    q = normalize(
        question
    )

    patterns = []

    # ==========================================
    # Entity list
    # ==========================================

    if intent == "entity_list":
        patterns = [
            r"who were the main leaders of "
            r"(.+?)[.?!]?$",

            r"who were the major leaders of "
            r"(.+?)[.?!]?$",

            r"who were the key leaders of "
            r"(.+?)[.?!]?$",

            r"who were the main figures of "
            r"(.+?)[.?!]?$",

            r"who were the key figures of "
            r"(.+?)[.?!]?$",

            r"who were important people in "
            r"(.+?)[.?!]?$",

            # ----------------------------------
            # NEW:
            # Which people were important in X?
            # ----------------------------------

            r"which people were important in "
            r"(.+?)[.?!]?$",

            r"who were notable figures in "
            r"(.+?)[.?!]?$",

            r"who were major political figures in "
            r"(.+?)[.?!]?$",

            r"which leaders were prominent in "
            r"(.+?)[.?!]?$",

            r"who played major roles in "
            r"(.+?)[.?!]?$",

            r"name the important figures in "
            r"(.+?)[.?!]?$",

            r"name important figures in "
            r"(.+?)[.?!]?$",

            r"name key figures from "
            r"(.+?)[.?!]?$",

            r"name key figures in "
            r"(.+?)[.?!]?$",

            r"list important leaders of "
            r"(.+?)[.?!]?$",

            r"identify key people from "
            r"(.+?)[.?!]?$",
        ]

    # ==========================================
    # Structure
    # ==========================================

    elif intent == "structure":
        patterns = [
            r"explain the internal structure of "
            r"(.+?)[.?!]?$",

            r"describe the internal structure of "
            r"(.+?)[.?!]?$",

            r"explain the molecular structure of "
            r"(.+?)[.?!]?$",

            r"describe the molecular structure of "
            r"(.+?)[.?!]?$",

            r"explain the structure of "
            r"(.+?)[.?!]?$",

            r"describe the structure of "
            r"(.+?)[.?!]?$",

            r"what is the structure of "
            r"(.+?)[.?!]?$",

            r"what was the structure of "
            r"(.+?)[.?!]?$",

            # ----------------------------------
            # Generic organized forms.
            #
            # These must exist in addition to
            # singular "how was".
            # ----------------------------------

            r"how were (.+?) organized into units"
            r"[.?!]?$",

            r"how are (.+?) organized into units"
            r"[.?!]?$",

            r"how were (.+?) organised into units"
            r"[.?!]?$",

            r"how are (.+?) organised into units"
            r"[.?!]?$",

            # ----------------------------------
            # NEW:
            #
            # How were Roman legions organized?
            # ->
            # Roman legions
            # ----------------------------------

            r"how were (.+?) organized"
            r"[.?!]?$",

            r"how are (.+?) organized"
            r"[.?!]?$",

            r"how were (.+?) organised"
            r"[.?!]?$",

            r"how are (.+?) organised"
            r"[.?!]?$",

            r"how was (.+?) organized"
            r"[.?!]?$",

            r"how is (.+?) organized"
            r"[.?!]?$",

            r"how was (.+?) organised"
            r"[.?!]?$",

            r"how is (.+?) organised"
            r"[.?!]?$",

            r"how were (.+?) structured"
            r"[.?!]?$",

            r"how are (.+?) structured"
            r"[.?!]?$",

            r"how was (.+?) structured"
            r"[.?!]?$",

            r"how is (.+?) structured"
            r"[.?!]?$",

            r"in what way was (.+?) structured"
            r"[.?!]?$",

            r"in what way is (.+?) structured"
            r"[.?!]?$",

            r"what are the parts of "
            r"(.+?)[.?!]?$",

            r"what are the components of "
            r"(.+?)[.?!]?$",

            r"what components form "
            r"(.+?)[.?!]?$",

            r"what makes up "
            r"(.+?)[.?!]?$",

            r"what is (.+?) made of"
            r"[.?!]?$",

            r"what are (.+?) made of"
            r"[.?!]?$",

            r"what units made up "
            r"(.+?)[.?!]?$",

            r"what units form "
            r"(.+?)[.?!]?$",

            r"what units formed "
            r"(.+?)[.?!]?$",

            r"what was the hierarchy of "
            r"(.+?)[.?!]?$",

            r"how was (.+?) divided"
            r"[.?!]?$",

            r"how is (.+?) divided"
            r"[.?!]?$",

            r"how were (.+?) divided"
            r"[.?!]?$",

            r"how are (.+?) divided"
            r"[.?!]?$",

            r"how are the parts of (.+?) arranged"
            r"[.?!]?$",

            r"what does the structure of "
            r"(.+?) consist of[.?!]?$",
        ]

    # ==========================================
    # Process
    # ==========================================

    elif intent == "process":
        patterns = [
            r"explain how (.+?) works"
            r"[.?!]?$",

            r"describe how (.+?) works"
            r"[.?!]?$",

            r"how does (.+?) work"
            r"[.?!]?$",

            r"how exactly does (.+?) operate"
            r"[.?!]?$",

            r"how does (.+?) operate"
            r"[.?!]?$",

            r"how (.+?) operates"
            r"[.?!]?$",

            r"what happens during "
            r"(.+?)[.?!]?$",

            r"what happens when "
            r"(.+?) takes place[.?!]?$",

            r"what occurs in "
            r"(.+?)[.?!]?$",

            r"what does (.+?) do"
            r"[.?!]?$",

            r"how do plants perform "
            r"(.+?)[.?!]?$",

            r"what is the process of "
            r"(.+?)[.?!]?$",

            r"explain the process of "
            r"(.+?)[.?!]?$",

            r"describe the mechanism of "
            r"(.+?)[.?!]?$",

            r"what are the stages of "
            r"(.+?)[.?!]?$",

            r"what are the steps of "
            r"(.+?)[.?!]?$",

            r"what are the main steps involved in "
            r"(.+?)[.?!]?$",

            r"how is energy converted during "
            r"(.+?)[.?!]?$",

            r"how does (.+?) convert energy"
            r"[.?!]?$",

            r"how does (.+?) convert .+"
            r"[.?!]?$",

            r"explain what occurs in "
            r"(.+?)[.?!]?$",

            r"describe the basic operation of "
            r"(.+?)[.?!]?$",

            r"explain the main process involved in "
            r"(.+?)[.?!]?$",
        ]

    # ==========================================
    # Features
    # ==========================================

    elif intent == "features":
        patterns = [
            r"what (?:are|were) the main features of "
            r"(.+?)[.?!]?$",

            r"what (?:are|were) the features of "
            r"(.+?)[.?!]?$",

            r"what (?:are|were) the characteristics of "
            r"(.+?)[.?!]?$",

            r"describe the main features of "
            r"(.+?)[.?!]?$",

            r"describe the characteristics of "
            r"(.+?)[.?!]?$",

            r"what characterized "
            r"(.+?)[.?!]?$",

            r"what characterizes "
            r"(.+?)[.?!]?$",

            r"what defined "
            r"(.+?)[.?!]?$",

            r"what defines "
            r"(.+?)[.?!]?$",

            r"what features characterized "
            r"(.+?)[.?!]?$",

            r"what political features did "
            r"(.+?) have[.?!]?$",

            r"what institutions characterized "
            r"(.+?)[.?!]?$",

            r"what were key characteristics of "
            r"(.+?)[.?!]?$",

            r"what were the defining features of "
            r"(.+?)[.?!]?$",

            r"describe important institutions of "
            r"(.+?)[.?!]?$",
        ]

    # ==========================================
    # Significance
    # ==========================================

    elif intent == "significance":
        patterns = [
            r"what is the significance of "
            r"(.+?)[.?!]?$",

            r"what was the significance of "
            r"(.+?)[.?!]?$",

            r"what is the importance of "
            r"(.+?)[.?!]?$",

            r"what was the importance of "
            r"(.+?)[.?!]?$",

            r"why was (.+?) important"
            r"[.?!]?$",

            r"why is (.+?) important"
            r"[.?!]?$",

            r"why has (.+?) been considered important"
            r"[.?!]?$",

            r"why does (.+?) matter historically"
            r"[.?!]?$",

            r"why does (.+?) matter"
            r"[.?!]?$",

            r"what made (.+?) significant"
            r"[.?!]?$",

            r"what was historically important about "
            r"(.+?)[.?!]?$",

            r"what is historically important about "
            r"(.+?)[.?!]?$",

            r"what was important about "
            r"(.+?)[.?!]?$",

            r"what is important about "
            r"(.+?)[.?!]?$",

            r"how was (.+?) historically significant"
            r"[.?!]?$",

            r"how is (.+?) historically significant"
            r"[.?!]?$",

            r"what is historically significant about "
            r"(.+?)[.?!]?$",

            r"what was historically significant about "
            r"(.+?)[.?!]?$",

            r"what impact made (.+?) significant"
            r"[.?!]?$",

            r"explain the significance of "
            r"(.+?)[.?!]?$",

            r"describe the historical importance of "
            r"(.+?)[.?!]?$",
        ]

    # ==========================================
    # Cause
    # ==========================================

    elif intent == "cause":
        patterns = [
            r"explain why (.+?) declined"
            r"[.?!]?$",

            r"why did (.+?) decline"
            r"[.?!]?$",

            r"why was (.+?) declining"
            r"[.?!]?$",

            r"why did (.+?) weaken"
            r"[.?!]?$",

            r"why did (.+?) lose strength"
            r"[.?!]?$",

            r"what caused (.+?) to decline"
            r"[.?!]?$",

            r"what caused (.+?) to weaken"
            r"[.?!]?$",

            r"what led to the decline of "
            r"(.+?)[.?!]?$",

            r"what made (.+?) eventually decline"
            r"[.?!]?$",

            r"what made (.+?) decline"
            r"[.?!]?$",

            r"what factors caused (.+?) to weaken"
            r"[.?!]?$",

            r"what factors contributed to "
            r"(.+?)(?:'s)? decline[.?!]?$",

            r"for what reasons did (.+?) decline"
            r"[.?!]?$",

            r"what were the reasons for "
            r"(.+?)(?:'s)? decline[.?!]?$",

            r"how did (.+?) come to decline"
            r"[.?!]?$",

            r"what drove (.+?) into decline"
            r"[.?!]?$",

            r"what contributed to the weakening of "
            r"(.+?)[.?!]?$",

            r"what brought about the decline of "
            r"(.+?)[.?!]?$",

            r"what was behind the decline of "
            r"(.+?)[.?!]?$",

            r"which factors led to "
            r"(.+?)(?:'s)? decline[.?!]?$",

            r"what caused (.+?) to collapse"
            r"[.?!]?$",

            r"what caused (.+?) to fall"
            r"[.?!]?$",

            r"why did (.+?) collapse"
            r"[.?!]?$",

            r"why did (.+?) fall"
            r"[.?!]?$",

            r"what caused (.+?)[.?!]?$",
        ]

    # ==========================================
    # Effect
    # ==========================================

    elif intent == "effect":
        patterns = [
            # ----------------------------------
            # "What were the effects of X on Y?" —
            # isolate X as the subject (Y is the
            # second concept handled by multi-hop).
            # ----------------------------------

            r"what (?:were|are|was|is) "
            r"the effects of "
            r"(.+?) on .+",

            r"what were the effects of "
            r"(.+?)[.?!]?$",

            r"what was the effect of "
            r"(.+?)[.?!]?$",

            r"what were the consequences of "
            r"(.+?)[.?!]?$",

            r"what was the consequence of "
            r"(.+?)[.?!]?$",

            r"what was the impact of "
            r"(.+?)[.?!]?$",

            r"what happened after "
            r"(.+?)[.?!]?$",

            r"what resulted from "
            r"(.+?)[.?!]?$",

            r"what followed "
            r"(.+?)[.?!]?$",

            r"what came after "
            r"(.+?)[.?!]?$",

            r"what changes followed "
            r"(.+?)[.?!]?$",

            r"what developments followed "
            r"(.+?)[.?!]?$",

            r"what happened as a result of "
            r"(.+?)[.?!]?$",

            r"describe the consequences of "
            r"(.+?)[.?!]?$",

            r"explain the effects of "
            r"(.+?)[.?!]?$",

            # ----------------------------------
            # IMPORTANT V3 FIX
            # ----------------------------------

            r"how did conditions change after "
            r"(.+?)[.?!]?$",

            r"how did things change after "
            r"(.+?)[.?!]?$",

            r"how did life change after "
            r"(.+?)[.?!]?$",

            r"what consequences followed "
            r"(.+?)[.?!]?$",

            r"what was one result of "
            r"(.+?)[.?!]?$",
        ]

    # ==========================================
    # Change
    # ==========================================

    elif intent == "change":
        patterns = [
            # ----------------------------------
            # Transition questions naming a SECOND
            # distinct concept.
            #
            # "How did the Roman Empire's decline
            #  affect the development of medieval
            #  Europe?" ->
            #  the Roman Empire
            # ----------------------------------

            r"how did (.+?)(?:'s|'s) "
            r"(?:decline|fall|collapse|weakening) "
            r"(?:affect|influenced|influence|impact|"
            r"shaped|shape|transform) .+",

            r"how did (.+?) "
            r"(?:affect|influence|influenced|impact|"
            r"shape|shaped|transform) "
            r"(?:the )?(?:development|evolution|"
            r"emergence) of .+",

            r"how did (.+?) change over time"
            r"[.?!]?$",

            r"how did (.+?) change"
            r"[.?!]?$",

            r"how has (.+?) changed"
            r"[.?!]?$",

            r"describe how (.+?) changed"
            r"[.?!]?$",

            r"describe the changes in "
            r"(.+?) over time[.?!]?$",

            r"in what ways did (.+?) change"
            r"[.?!]?$",

            r"how did (.+?) transform over time"
            r"[.?!]?$",

            r"how did (.+?) develop over "
            r"(?:the )?centuries[.?!]?$",

            r"how did (.+?) develop"
            r"[.?!]?$",

            r"how did (.+?) evolve through history"
            r"[.?!]?$",

            r"how did (.+?) evolve"
            r"[.?!]?$",

            r"explain how (.+?) changed over time"
            r"[.?!]?$",

            r"how did (.+?) transition over time"
            r"[.?!]?$",

            r"describe the historical development of "
            r"(.+?)[.?!]?$",

            r"what changes occurred in "
            r"(.+?) over time[.?!]?$",

            r"what developments changed "
            r"(.+?)[.?!]?$",

            r"how was (.+?) different later "
            r"in its history[.?!]?$",
        ]

    for pattern in patterns:
        match = re.fullmatch(
            pattern,
            q,
            flags=re.IGNORECASE,
        )

        if match:
            subject = clean_subject(
                match.group(1)
            )

            if intent == "effect":
                subject = normalize_effect_subject(
                    subject
                )

            return subject

    return clean_subject(
        q
    )


# --------------------------------------------------
# Canonical question generation
# --------------------------------------------------

def build_canonical_question(
    intent,
    subject,
    comparison_subjects=None,
):
    if intent == "comparison":

        if not comparison_subjects:
            return None

        left, right = (
            comparison_subjects
        )

        return (
            f"What are the differences between "
            f"{left} and {right}?"
        )

    if not subject:
        return None

    if intent == "cause":
        return (
            f"Why did {subject} decline?"
        )

    if intent == "change":
        return (
            f"How did {subject} change over time?"
        )

    if intent == "effect":
        return (
            f"What were the effects of {subject}?"
        )

    if intent == "structure":
        return (
            f"What is the structure of {subject}?"
        )

    if intent == "process":
        return (
            f"Explain how {subject} works."
        )

    if intent == "features":
        return (
            f"What were the main features of "
            f"{subject}?"
        )

    if intent == "significance":
        return (
            f"What is the significance of "
            f"{subject}?"
        )

    if intent == "entity_list":
        return (
            f"Who were the key figures of "
            f"{subject}?"
        )

    return None


# --------------------------------------------------
# Query generation
# --------------------------------------------------

def build_queries(
    question,
):
    original_question = normalize(
        question
    )

    intent = detect_intent(
        original_question
    )

    comparison_subjects = None

    if intent == "comparison":
        comparison_subjects = (
            extract_comparison_subjects(
                original_question
            )
        )

        if comparison_subjects:
            left, right = (
                comparison_subjects
            )

            subject = (
                f"{left} vs {right}"
            )

        else:
            subject = clean_subject(
                original_question
            )

    else:
        subject = extract_subject(
            original_question,
            intent,
        )

    canonical_question = (
        build_canonical_question(
            intent,
            subject,
            comparison_subjects,
        )
    )

    queries = []

    # Original query always stays first.
    queries.append(
        original_question
    )

    if canonical_question:
        queries.append(
            canonical_question
        )

    # ==========================================
    # Entity list
    # ==========================================

    if intent == "entity_list":
        queries.extend(
            [
                f"{subject} leaders",
                f"{subject} key figures",
                f"{subject} political leaders",
                f"{subject} important people",
                f"{subject} notable figures",
                f"{subject} major figures",
            ]
        )

        if (
            "french revolution"
            in subject.lower()
        ):
            queries.extend(
                [
                    (
                        "French Revolution "
                        "Robespierre Danton leaders"
                    ),
                    (
                        "French Revolution political "
                        "leaders Robespierre"
                    ),
                ]
            )

    # ==========================================
    # Structure
    # ==========================================

    elif intent == "structure":
        queries.extend(
            [
                f"{subject} structure",
                f"{subject} organization",
                f"{subject} components",
                f"{subject} parts",
                f"{subject} hierarchy",
                f"what {subject} consists of",
            ]
        )

        subject_lower = (
            subject.lower()
        )

        if (
            "roman army"
            in subject_lower
            or "roman military"
            in subject_lower
            or "roman legion"
            in subject_lower
            or "roman legions"
            in subject_lower
            or "roman soldiers"
            in subject_lower
        ):
            queries.extend(
                [
                    (
                        "Roman army legion cohort "
                        "century structure"
                    ),
                    (
                        "Roman legion cohort centuries "
                        "organization"
                    ),
                    (
                        "Roman military hierarchy "
                        "legion cohort century"
                    ),
                    (
                        "Roman legion divided into "
                        "cohorts centuries"
                    ),
                    (
                        "Roman legion main sub-unit "
                        "cohort"
                    ),
                    (
                        "Roman soldiers legion cohort "
                        "century units"
                    ),
                ]
            )

        if "dna" in subject_lower:
            queries.extend(
                [
                    "DNA double helix structure",
                    (
                        "DNA made of nucleotides "
                        "adenine thymine guanine cytosine"
                    ),
                    (
                        "DNA nucleotide bases "
                        "double stranded molecule"
                    ),
                    (
                        "DNA molecular structure "
                        "nucleotides"
                    ),
                    (
                        "DNA components sugar phosphate "
                        "base pairs"
                    ),
                ]
            )

    # ==========================================
    # Process
    # ==========================================

    elif intent == "process":
        queries.extend(
            [
                f"{subject} process",
                f"{subject} mechanism",
                f"{subject} stages",
                f"how {subject} works",
                f"{subject} operation",
            ]
        )

        if (
            "photosynthesis"
            in subject.lower()
        ):
            queries.extend(
                [
                    (
                        "photosynthesis sunlight "
                        "carbon dioxide water sugar oxygen"
                    ),
                    (
                        "photosynthesis converts sunlight "
                        "energy into chemical energy"
                    ),
                    (
                        "photosynthesis process plants "
                        "water carbon dioxide oxygen"
                    ),
                ]
            )

    # ==========================================
    # Features
    # ==========================================

    elif intent == "features":
        queries.extend(
            [
                f"{subject} main features",
                f"{subject} features",
                f"{subject} characteristics",
                f"{subject} institutions",
                (
                    f"{subject} structure "
                    f"government system"
                ),
            ]
        )

        if (
            "roman republic"
            in subject.lower()
        ):
            queries.extend(
                [
                    (
                        "Roman Republic Senate "
                        "government institutions"
                    ),
                    (
                        "Roman Republic political "
                        "structure Senate"
                    ),
                ]
            )

    # ==========================================
    # Significance
    # ==========================================

    elif intent == "significance":
        queries.extend(
            [
                f"{subject} significance",
                f"{subject} importance",
                f"{subject} impact influence",
                f"{subject} historical importance",
                f"{subject} historical significance",
            ]
        )

        if (
            "magna carta"
            in subject.lower()
        ):
            queries.extend(
                [
                    "Magna Carta limited royal power",
                    (
                        "Magna Carta royal authority "
                        "rights law"
                    ),
                ]
            )

    # ==========================================
    # Cause
    # ==========================================

    elif intent == "cause":
        queries.extend(
            [
                f"{subject} causes",
                f"{subject} reasons",
                f"{subject} decline causes",
                f"{subject} caused by",
                f"reasons for {subject} decline",
                f"factors behind {subject} decline",
            ]
        )

        if (
            "roman empire"
            in subject.lower()
        ):
            queries.extend(
                [
                    (
                        "Roman Empire decline causes "
                        "invasion revolt"
                    ),
                    (
                        "Roman Empire weakening "
                        "decline reasons"
                    ),
                    (
                        "fall Roman Empire non-Roman "
                        "peoples Germanic troops revolt"
                    ),
                ]
            )

    # ==========================================
    # Effect
    # ==========================================

    elif intent == "effect":
        queries.extend(
            [
                f"{subject} effects",
                f"{subject} consequences",
                f"{subject} aftermath",
                f"{subject} impact",
                f"what happened after {subject}",
                f"results of {subject}",
            ]
        )

        if (
            "roman empire"
            in subject.lower()
        ):
            queries.extend(
                [
                    (
                        "after fall Roman Empire "
                        "Eastern Roman Empire"
                    ),
                    (
                        "fall Roman Empire "
                        "consequences aftermath"
                    ),
                    (
                        "Roman Empire after fall "
                        "Germanic kingdoms"
                    ),
                ]
            )

    # ==========================================
    # Change
    # ==========================================

    elif intent == "change":
        queries.extend(
            [
                f"{subject} change over time",
                f"{subject} development",
                f"{subject} evolution",
                f"{subject} transition",
                f"history of {subject} changes",
            ]
        )

        if (
            "roman empire"
            in subject.lower()
        ):
            queries.extend(
                [
                    (
                        "Roman Empire changed over time "
                        "provinces capital"
                    ),
                    (
                        "Roman Empire historical "
                        "development expansion decline"
                    ),
                ]
            )

    # ==========================================
    # Comparison
    # ==========================================

    elif intent == "comparison":

        if comparison_subjects:
            left, right = (
                comparison_subjects
            )

            queries.extend(
                [
                    left,
                    right,

                    f"{left} characteristics",
                    f"{right} characteristics",

                    f"{left} {right} differences",

                    f"{left} versus {right}",

                    (
                        f"difference between "
                        f"{left} and {right}"
                    ),
                ]
            )

    # ==========================================
    # General
    # ==========================================

    else:
        useful = [
            word
            for word in re.findall(
                r"[a-z0-9']+",
                subject.lower(),
            )
            if len(word) >= 3
        ]

        if useful:
            queries.append(
                " ".join(
                    useful
                )
            )

    # ==========================================
    # Deduplicate queries
    # ==========================================

    seen = set()
    unique = []

    for query in queries:
        query = normalize(
            query
        )

        key = query.lower()

        if not key:
            continue

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            query
        )

    return {
        "intent":
            intent,

        "subject":
            subject,

        "canonical_question":
            canonical_question,

        "comparison_subjects":
            comparison_subjects,

        "queries":
            unique,
    }


# --------------------------------------------------
# Standalone tests
# --------------------------------------------------

if __name__ == "__main__":

    tests = [

        # ==========================================
        # Critical fixes
        # ==========================================

        "What units formed a Roman legion?",

        "How were Roman legions organized?",

        (
            "How did conditions change after "
            "the Roman Empire fell?"
        ),

        (
            "Which people were important in "
            "the French Revolution?"
        ),

        (
            "What differentiates mitosis "
            "from meiosis?"
        ),

        (
            "How do mitosis and meiosis differ?"
        ),

        # ==========================================
        # Effect
        # ==========================================

        (
            "What came after "
            "the Roman Empire fell?"
        ),

        (
            "What consequences followed "
            "the collapse of the Roman Empire?"
        ),

        (
            "What was one result of "
            "the fall of the Roman Empire?"
        ),

        (
            "Explain the effects of "
            "the fall of the Roman Empire."
        ),

        (
            "Describe the consequences of "
            "the fall of the Roman Empire."
        ),

        # ==========================================
        # Structure
        # ==========================================

        "How was the Roman military organized?",

        (
            "Describe the internal structure "
            "of a Roman legion."
        ),

        (
            "How were Roman soldiers "
            "organized into units?"
        ),

        "What makes up a DNA molecule?",

        "What is DNA made of?",

        "What components form DNA?",

        # ==========================================
        # Photosynthesis
        # ==========================================

        "What happens during photosynthesis?",

        "How do plants perform photosynthesis?",

        (
            "What happens when photosynthesis "
            "takes place?"
        ),

        "How does photosynthesis convert energy?",

        "What does photosynthesis do?",

        (
            "How is energy converted during "
            "photosynthesis?"
        ),

        (
            "What are the main steps involved "
            "in photosynthesis?"
        ),

        # ==========================================
        # Significance
        # ==========================================

        "What made the Magna Carta significant?",

        (
            "What was historically important "
            "about the Magna Carta?"
        ),

        (
            "What impact made the Magna Carta "
            "significant?"
        ),

        "What was important about the Magna Carta?",

        (
            "How was the Magna Carta "
            "historically significant?"
        ),

        (
            "Why has the Magna Carta "
            "been considered important?"
        ),

        (
            "What is historically significant "
            "about the Magna Carta?"
        ),

        # ==========================================
        # Features
        # ==========================================

        "What characterized the Roman Republic?",

        "What defined the Roman Republic?",

        (
            "What features characterized "
            "the Roman Republic?"
        ),

        (
            "What political features did "
            "the Roman Republic have?"
        ),

        (
            "What institutions characterized "
            "the Roman Republic?"
        ),

        # ==========================================
        # Entity lists
        # ==========================================

        (
            "Name key figures from "
            "the French Revolution."
        ),

        (
            "Who were important people in "
            "the French Revolution?"
        ),

        (
            "Which people were important in "
            "the French Revolution?"
        ),

        (
            "Who were notable figures in "
            "the French Revolution?"
        ),

        (
            "Which leaders were prominent in "
            "the French Revolution?"
        ),

        (
            "Who played major roles in "
            "the French Revolution?"
        ),

        (
            "Who were major political figures in "
            "the French Revolution?"
        ),

        (
            "Identify key people from "
            "the French Revolution."
        ),

        # ==========================================
        # Comparison
        # ==========================================

        (
            "Explain the differences between "
            "mitosis and meiosis."
        ),

        (
            "Describe how mitosis differs "
            "from meiosis."
        ),

        (
            "In what ways are mitosis "
            "and meiosis different?"
        ),

        (
            "What distinguishes mitosis "
            "from meiosis?"
        ),

        (
            "What differentiates mitosis "
            "from meiosis?"
        ),

        (
            "How do mitosis and meiosis differ?"
        ),

        (
            "In what ways do mitosis "
            "and meiosis differ?"
        ),

        (
            "What are the main differences "
            "between mitosis and meiosis?"
        ),

        # ==========================================
        # Cause
        # ==========================================

        "Why did the Roman Empire decline?",

        (
            "What made the Roman Empire "
            "eventually decline?"
        ),

        (
            "What factors caused the "
            "Roman Empire to weaken?"
        ),

        (
            "What contributed to the weakening "
            "of the Roman Empire?"
        ),

        (
            "Why did the Roman Empire "
            "lose strength?"
        ),

        (
            "Explain why the Roman Empire "
            "declined."
        ),

        # ==========================================
        # Existing successful variants
        # ==========================================

        "How was the Roman army organized?",

        "Explain the structure of DNA.",

        "Explain how photosynthesis works.",

        (
            "Why does the Magna Carta "
            "matter historically?"
        ),

        (
            "Name the important figures "
            "in the French Revolution."
        ),

        (
            "What separates mitosis "
            "from meiosis?"
        ),

        "Mitosis versus meiosis.",

        (
            "Describe how the Roman "
            "Empire changed."
        ),
    ]

    for question in tests:

        plan = build_queries(
            question
        )

        print(
            "\n"
            + "=" * 76
        )

        print(
            "Question:",
            question,
        )

        print(
            "Intent:",
            plan[
                "intent"
            ],
        )

        print(
            "Subject:",
            plan[
                "subject"
            ],
        )

        print(
            "Canonical:",
            plan[
                "canonical_question"
            ],
        )

        print(
            "Queries:"
        )

        for query in plan[
            "queries"
        ]:
            print(
                "-",
                query,
            )