"""
The code in this file was adapted from ReViz.
See the license of ReViz below:

------------------------------------------------------------------------------
MIT License

Copyright (c) 2019 l-hartung

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
------------------------------------------------------------------------------
"""

import os
import re
import json
import hashlib
from wasabi import msg
from thefuzz import fuzz
import xml.etree.ElementTree as et

global user_answers
user_answers = []


def key_to_md5(key):
    """
    convert bibtex-key to shortened md5-sum to avoid special characters
    in the keys.

    :param key: bibtex-key of an article
    :return: converted key, first six characters of the key md5-sum
    """
    m = hashlib.md5()
    m.update(key.encode("utf-8"))
    hd = m.hexdigest()
    shorthd = hd[:6]
    if shorthd.isdigit():
        return shorthd + "a"
    return shorthd


def find_urls(string):
    """
    Check if the given string contains an url,
    used to find the pdfs of all articles.

    :param string: link to the pdf of an article
    :return: url if one is found
    """
    url = re.findall(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        string,
    )
    return url


def find_author(author_json):
    """
    detect correct surnames of all authors out of the author-bibtex-field
    :param author_json: author-field of an article from json export
    :return: list of all surnames
    """
    if "," not in author_json:
        pattern = re.compile(r"(?P<name>[A-Za-z\-]+)(?: +and +| +AND +|$)")
    else:
        pattern = re.compile(r"(?:^|and +|AND +)(?P<name>[A-Za-z\- ]+)")
    authors = pattern.findall(author_json)
    return authors


def find_doi(input):
    """
    checks if the doi of an article is syntactically correct or empty
    :param input: doi of an article
    :return: correct doi if found, otherwise None
    """
    if input is None:
        return None
    regex = r"(\d\d\.\d+\/\S+)"
    regex = re.compile(regex)
    m = regex.search(input)
    if m is not None:
        return m.group()
    return None


def find_matching_authors(artauthors, otherauthors):
    """
    calculates the total number of authors and the number of shared authors
    taking into account first authors
    :param artauthors: authors of first examined article
    :param otherauthors: authors of second article
    :return: two paramenters to calculate the score of the two articles
    """
    counter = 0
    number = len(artauthors) + len(otherauthors)
    if len(artauthors) == 0 or len(otherauthors) == 0:
        return counter, number
    for author in artauthors:
        if author == artauthors[0]:
            if author == otherauthors[0]:
                counter += 5
                number -= 1
            elif (
                next(
                    (
                        a
                        for a in otherauthors
                        if fuzz.ratio(author.upper(), a.upper()) >= 95
                    ),
                    None,
                )
                is not None
            ):
                counter += 3
                number -= 1
        elif author == otherauthors[0]:
            counter += 3
            number -= 1
        elif (
            next(
                (
                    a
                    for a in otherauthors
                    if fuzz.ratio(author.upper(), a.upper()) >= 95
                ),
                None,
            )
            is not None
        ):
            counter += 1
            number -= 1
    return counter, number


def citation_matching(
    doi_art,
    doi_ref,
    title_art,
    title_ref,
    author_art,
    authors_ref,
    without_interactive_queries,
):
    """
    Checks if a reference and an article of the citation graph match,
    if yes a citation is found.

    :param doi_art: doi of the article
    :param doi_ref: doi of the reference
    :param title_art: article title
    :param title_ref: reference title
    :param author_art: article authors
    :param authors_ref: reference authors
    :param without_interactive_queries: true for interactive mode
    :return: True iff a match is found
    """

    def ask_user(title_art, title_ref, author_art, authors_ref):

        global user_answers

        if without_interactive_queries:
            return False
        else:

            # Check if user already answered this question before
            question = (title_art, title_ref, author_art, authors_ref)
            for user_answer in user_answers:
                if user_answer["question"] == question:
                    return user_answer["answer"]

            # Prompt a question to the user and get his answer
            msg.warn("Unsure whether the entries belong together or not:")
            print(
                "Article:  Title = "
                + title_art
                + "\n\t  Authors = "
                + str(author_art).strip("[]")
                + "\nReference: Title = "
                + title_ref
                + "\n\t Authors = "
                + str(authors_ref).strip("[]")
            )

            msg.text(
                "Do both entries belong to the same article?",
                color="grey",
            )
            msg.text(
                "Please enter 'y' or 'n'...",
                color="grey",
            )
            if input() == "y":
                user_answers.append({"question": question, "answer": True})
                return True
            else:
                user_answers.append({"question": question, "answer": False})
                return False

    doi_art = find_doi(doi_art)
    doi_ref = find_doi(doi_ref)

    if doi_art == doi_ref and doi_art is not None and doi_ref is not None:
        # That was easy, DOIs match.
        return True

    elif type(title_art) == str and type(title_ref) == str:

        # Normalize titles
        clean_title_art = title_art.replace("{", "").replace("}", "").upper()
        clean_title_ref = title_ref.replace("{", "").replace("}", "").upper()

        # Get similarity between titles
        lev = fuzz.ratio(clean_title_art, clean_title_ref)
        lev_partial = fuzz.partial_ratio(clean_title_art, clean_title_ref)

        if lev > 90 or (lev_partial > 95 and lev > 70):
            # Titles can be considered matching.
            counter, number = find_matching_authors(author_art, authors_ref)

            if counter >= 2:
                # Authors can be considered matching.
                return True
            else:
                # Authors seem not to match. Ask the user for help!
                return ask_user(
                    clean_title_art, clean_title_ref, author_art, authors_ref
                )

        elif lev_partial > 90 and lev > 60:
            # Titles seem not to match. Ask the user for help!
            return ask_user(
                clean_title_art, clean_title_ref, author_art, authors_ref
            )

        else:
            # Consider it certain that the titles do not match.
            return False
    else:
        return False


def build_graph_model(
    json_bib_file,
    tei,
    graph_dir,
    graph_filename,
    original_bibtex_keys,
    without_interactive_queries,
):
    """
    Output looks like this:
        {
        "years": [2017, 2016, 2019, 2019, 2020, 2019,...],
        "year_arts": {
            "2010": ["Hoffmann et al (2010)"],
            "2011": ["Weng et al (2011)", "Tu et al (2011)"]
            ...
        },
        "articles": [
            {
            "title": "Bootstrapping for {Numerical} {Open} {IE}",
            "author": ["Saha", "Pal"],
            "key": "Saha et al (2017)",
            "year": "2017"
            },
            {
            "title": "Numerical Relation Extraction with Minimal Supervision",
            "author": ["Madaan", "Mittal"],
            "key": "Madaan and Mittal (2016)",
            "year": "2016"
            }
            ...
        ],
        "edges": [
            {
            "from": "Saha et al (2017)",
            "to": "Hoffmann et al (2010)"
            },
            {
            "from": "Saha et al (2017)",
            "to": "Madaan and Mittal (2016)"
            },
            ...
        ]
    }"""
    msg.divider("Build citation graph model from references in PDFs")

    with open(json_bib_file, "r") as file:  # encoding='utf8'
        bib = json.load(file)

    articles = bib["final selection articles"]

    if not (original_bibtex_keys):
        for article in articles:
            article["bibtex_key"] = key_to_md5(article["bibtex_key"])

    # Init graph
    graph = {}

    # Add years (e.g., "years": [2017, 2016, 2019, 2019, 2020, 2019,...])
    years = []
    for article in articles:
        if article["year"] is not None:
            years.append(int(article["year"]))

    graph["years"] = years

    # Add year_arts
    graph["year_arts"] = {}
    for year in range(min(years), max(years) + 1):
        this_year_arts = []
        for article in articles:
            if int(article["year"]) == year:
                this_year_arts.append(article["bibtex_key"])
        graph["year_arts"][year] = this_year_arts

    # Add articles
    graph["articles"] = []
    for article in articles:
        authors = find_author(article["author"])
        article_dict = {
            "title": article["title"],
            "author": authors,
            "key": article["bibtex_key"],
            "year": article["year"],
        }
        graph["articles"].append(article_dict)

    # Add edges
    graph["edges"] = []
    namespace = "{http://www.tei-c.org/ns/1.0}"

    for article in articles:

        # Check if field for file references is used
        if article["file"] is None:
            continue

        # Get filename of TEI corresponding to PDF
        xmlName = os.path.basename(article["file"])[:-4]
        tei_file = os.path.join(tei, "{}.tei.xml".format(xmlName))

        # Check if TEI file exists
        if not os.path.isfile(tei_file):
            msg.fail("tei-file not found for " + article["title"])
            continue

        # Check if TEI content is empty
        with open(tei_file, "r", encoding="utf8") as f:
            tei_content = f.read()

        if tei_content in [
            "[NO_BLOCKS] PDF parsing resulted in empty content",
            "[BAD_INPUT_DATA] PDF to XML conversion failed with error code: 1",
        ]:
            msg.fail("tei-file is empty for", article["title"])
            continue

        print("")
        msg.text("Processing " + tei_file, color="blue")

        # Loop over all references that Grobid found
        xml = et.parse(tei_file)
        for ref in xml.findall(".//{}biblStruct".format(namespace)):

            # Get title of referenced paper
            ref_title = ref.find(".//{}title".format(namespace)).text
            ref_title = ref_title  # if ref_title is not None else 'Ohne Titel'

            # Get DOI of referenced paper
            if (
                ref.find('.//{}idno[@type="doi"]'.format(namespace))
                is not None
            ):
                ref_doi = ref.find(
                    './/{}idno[@type="doi"]'.format(namespace)
                ).text
            else:
                ref_doi = None

            # Get authors of referenced paper
            ref_authors = []
            for ref_author in ref.findall(".//{}surname".format(namespace)):
                ref_authors.append(ref_author.text)

            # Check if the referenced paper is included in the
            # given set of papers. If so, add an edge between
            # the current paper and the referenced paper.
            for art in articles:
                art_authors = find_author(art.get("author"))
                art_doi = art.get("doi")

                if art["title"] is article["title"]:
                    # An article cannot cite itself
                    continue

                elif citation_matching(
                    art_doi,
                    ref_doi,
                    art["title"],
                    ref_title,
                    art_authors,
                    ref_authors,
                    without_interactive_queries,
                ):
                    # This article matches the references, therefore add an
                    # edge between this article and the article referencing
                    # this article.
                    edge = {
                        "from": article["bibtex_key"],
                        "to": art["bibtex_key"],
                    }
                    graph["edges"].append(edge)
                    break

    with open(os.path.join(graph_dir, graph_filename), "w") as jf:
        json.dump(graph, jf, indent=2)
