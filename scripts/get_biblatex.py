import requests
from bs4 import BeautifulSoup
import re
import pickle


class GetBiblatex:
    def __init__(self, doi, diag_bib, kind):
        self.doi = doi
        self.diag_bib = diag_bib
        self.kind = kind

        # redirect to own directory
        with open(r"\accent_mappings.pkl", "rb") as f:
            accent_mappings = pickle.load(f)
        self.accent_mappings = accent_mappings

    def _get_doi_csl(self):
        response = requests.get(
            f"https://doi.org/{self.doi}",
            headers={"Accept": "application/vnd.citationstyles.csl+json"},
            timeout=5,
        )
        response.raise_for_status()

        return response.json()

    def _convert_to_biblatex_format(self, author_name):
        for char, biblatex_char in self.accent_mappings.items():
            author_name = author_name.replace(char, biblatex_char)
        return author_name

    @staticmethod
    def _clean_abstract_text(abstract_string):
        # remove the <jats> </jats> from abstract text
        abstract_string = re.sub(pattern='<jats:\w+>', repl='', string=abstract_string)
        abstract_string = re.sub(pattern='</jats:\w+>', repl='', string=abstract_string)

        return abstract_string

    def _get_doi_abstract(self):
        header = {"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"}
        response_request = requests.get(f"https://doi.org/{self.doi}", headers=header,)
        soup = BeautifulSoup(response_request.content, "html.parser")

        abstract_text = False
        try:
            response = self._get_doi_csl()
            abstract_string = response['abstract']
            abstract_text = self._clean_abstract_text(abstract_string)
            complete = True
        except (KeyError, TypeError):
            complete = False

        if not abstract_text:
            abstract_text = 'Abstract unavailable'
            while not complete:
                methods = [{"name": "dc.description"}, {"name": "dc.Description"}, {"name": "twitter.description"}, {"property": "og:description"}]
                for method in methods:
                    try:
                        abstract_string = soup.find("meta", method)["content"]
                        if abstract_string[-3:] != '...':   # prevent using partially available abstracts
                            abstract_text = abstract_string
                            break
                    except TypeError:
                        pass
                complete = True

        # clean up abstract text with newlines
        if "\r\n" in abstract_text:
            abstract_text = abstract_text.replace("\r\n", " ")
        if "\n\n" in abstract_text:
            abstract_text = abstract_text.replace("\n\n", " ")

        return abstract_text

    @staticmethod
    def _clean_author_abbreviation(auth_abr, year, bib_file):
        auth_abr = auth_abr+year
        substring_end = ","
        max_length = 3

        count = 0
        start_index = 0
        while True:
            start = bib_file.find(auth_abr, start_index)
            if start == -1:
                break
            end = bib_file.find(substring_end, start + len(auth_abr))
            if end == -1:
                break
            substring = bib_file[start+len(auth_abr):end]
            if len(substring) <= max_length:
                count += 1
            start_index = end + len(substring_end)

        letters = {1: 'a', 2: 'b', 3: 'c', 4: 'd', 5: 'e',
                   6: 'f', 7: 'g', 8: 'h', 9: 'i', 10: 'j',
                   11: 'k', 12: 'l', 13: 'm', 14: 'n', 15: 'o',
                   16: 'p', 17: 'q', 18: 'r', 19: 's', 20: 't',
                   21: 'u', 22: 'v', 23: 'w', 24: 'x', 25: 'y', 26: 'z'}

        if count != 0:
            for i in range(1, count+2):
                abbreviation = auth_abr+letters[i]
                if bib_file.count(abbreviation) == 0:
                    auth_abr = auth_abr + letters[i]
                    break

        return auth_abr

    def get_bib_text(self):
        try:
            response_json = self._get_doi_csl()
            abstract = self._get_doi_abstract()

            author_string = "{"
            for index, author in enumerate(response_json["author"]):
                if index == len(response_json["author"])-1:
                    if 'given' in author:
                        author_string = author_string + f"{author['family']}, {author['given']}" + "}"
                    else:
                        author_string = author_string + f"{author['family']} and "
                else:
                    if 'given' in author:
                        author_string = author_string + f"{author['family']}, {author['given']} and "
                    else:
                        author_string = author_string + f"{author['family']} and "

            newline = '\n'
            tab = '\t'
            author_abbreviation = response_json['author'][0]['family'][:4]
            year = str(response_json["published"]["date-parts"][0][0])[2:]
            author_abbreviation = self._clean_author_abbreviation(author_abbreviation, year, self.diag_bib)
            title = response_json["title"]
            optnote = "DIAG, RADIOLOGY"

            biblatex = f"@{self.kind}{{{author_abbreviation}, {newline}" \
                       f"{tab}author = {author_string}, {newline} " \
                       f"{tab}title = {{{title}}}, {newline}" \
                       f"{tab}doi = {{{response_json['DOI']}}}, {newline}" \
                       f"{tab}year = {{{response_json['published']['date-parts'][0][0]}}}, {newline}" \
                       f"{tab}abstract = {{{abstract}}}, {newline}" \
                       f"{tab}url = {{{response_json['URL']}}}, {newline}" \
                       f"{tab}file = {{{author_abbreviation}.pdf:pdf\\{author_abbreviation}.pdf:PDF}}, {newline}" \
                       f"{tab}optnote = {{{optnote}}}, {newline}" \
                       f"{tab}journal = {{{response_json['container-title']}}}, {newline}" \
                       f"{tab}citation-count = {{{response_json['is-referenced-by-count']}}}, {newline}" \
                       f"}}{newline}"
        except Exception as e:
            print(f'Unable to generate bibtext for {self.doi}')
            print(e)
            biblatex = 'empty'

        return biblatex