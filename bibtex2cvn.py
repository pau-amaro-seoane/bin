#!/usr/bin/env python3
import re
import sys

# --- Help Text ---
"""
This script takes your bib file from ADS/NASA and converts it to a format 
that the Spanish CVN cv editor will accept and display correctly.

It performs three main actions:
1.  Removes extra curly brackets {} from author names, which the CVN
    editor fails to parse correctly.
2.  Expands common astronomy journal macros (e.g., \\mnras) into their
    full names (e.g., Monthly Notices of the RAS).
3.  Converts LaTeX-style accents (e.g., V{\\'a}zquez) into their
    proper Unicode (UTF-8) characters (e.g., Vázquez).

HOW TO USE:
1.  Save this script as 'clean_bibtex_v2.py'.
2.  Open your terminal or command prompt.
3.  Run the script by passing your input bib file as an argument ($1).
4.  Redirect the output (stdout) to a new file.

Example command:
python clean_bibtex_v2.py your_ads_export.bib > cleaned_for_cvn.bib

CVN IMPORT TIP:
As this script mentions, if your bib file contains many entries, 
you will have to feed chunks of about 15 articles to the import 
in the CVN webpages because it does not seem to be able to digest 
more than that.
"""

# --- Configuration ---

# Dictionary for journal macro expansion
JOURNAL_MAP = {
    r'\aj': 'Astronomical Journal', r'\actaa': 'Acta Astronomica',
    r'\araa': 'Annual Review of Astron and Astrophys', r'\apj': 'Astrophysical Journal',
    r'\apjl': 'Astrophysical Journal, Letters', r'\apjs': 'Astrophysical Journal, Supplement',
    r'\ao': 'Applied Optics', r'\apss': 'Astrophysics and Space Science',
    r'\aap': 'Astronomy and Astrophysics', r'\aapr': 'Astronomy and Astrophysics Reviews',
    r'\aaps': 'Astronomy and Astrophysics, Supplement', r'\azh': 'Astronomicheskii Zhurnal',
    r'\baas': 'Bulletin of the AAS', r'\caa': 'Chinese Astronomy and Astrophysics',
    r'\cjaa': 'Chinese Journal of Astronomy and Astrophysics', r'\icarus': 'Icarus',
    r'\jcap': 'Journal of Cosmology and Astroparticle Physics',
    r'\jrasc': 'Journal of the RAS of Canada', r'\memras': 'Memoirs of the RAS',
    r'\mnras': 'Monthly Notices of the RAS', r'\na': 'New Astronomy',
    r'\nar': 'New Astronomy Review', r'\pra': 'Physical Review A: General Physics',
    r'\prb': 'Physical Review B: Solid State', r'\prc': 'Physical Review C',
    r'\prd': 'Physical Review D', r'\pre': 'Physical Review E',
    r'\prl': 'Physical Review Letters',
    r'\pasa': 'Publications of the Astron. Soc. of Australia',
    r'\pasp': 'Publications of the ASP', r'\pasj': 'Publications of the ASJ',
    r'\rmxaa': 'Revista Mexicana de Astronomia y Astrofisica',
    r'\qjras': 'Quarterly Journal of the RAS', r'\skytel': 'Sky and Telescope',
    r'\solphys': 'Solar Physics', r'\sovast': 'Soviet Astronomy',
    r'\ssr': 'Space Science Reviews', r'\zap': 'Zeitschrift fuer Astrophysik',
    r'\nat': 'Nature', r'\iaucirc': 'IAU Cirulars',
    r'\aplett': 'Astrophysics Letters', r'\apspr': 'Astrophysics Space Physics Research',
    r'\bain': 'Bulletin Astronomical Institute of the Netherlands',
    r'\fcp': 'Fundamental Cosmic Physics', r'\gca': 'Geochimica Cosmochimica Acta',
    r'\grl': 'Geophysics Research Letters', r'\jcp': 'Journal of Chemical Physics',
    r'\jgr': 'Journal of Geophysics Research',
    r'\jqsrt': 'Journal of Quantitiative Spectroscopy and Radiative Transfer',
    r'\memsai': 'Mem. Societa Astronomica Italiana', r'\nphysa': 'Nuclear Physics A',
    r'\physrep': 'Physics Reports', r'\physscr': 'Physica Scripta',
    r'\planss': 'Planetary Space Science', r'\procspie': 'Proceedings of the SPIE',
}

# Dictionary for LaTeX accent conversion to Unicode
ACCENT_MAP = {
    # Acute
    r"{\'{a}}": "á", r"{\'{e}}": "é", r"{\'{i}}": "í", r"{\'{o}}": "ó", r"{\'{u}}": "ú",
    r"{\'{A}}": "Á", r"{\'{E}}": "É", r"{\'{I}}": "Í", r"{\'{O}}": "Ó", r"{\'{U}}": "Ú",
    r"V{\'a}zquez": "Vázquez", r"Ver{\'o}nica": "Verónica",
    # Grave
    r"{\`a}": "à", r"{\`e}": "è", r"{\`i}": "ì", r"{\`o}": "ò", r"{\`u}": "ù",
    r"{\`A}": "À", r"{\`E}": "È", r"{\`I}": "Ì", r"{\`O}": "Ò", r"{\`U}": "Ù",
    r"Zolt{\'a}n": "Zoltán", r"M{\'a}rius": "Márius", r"{\'A}lvaro": "Álvaro",
    r"C{\'e}sar": "César", r"Garc{\'\i}a": "García", r"Mar{\'\i}n": "Marín",
    r"Mart{\'\i}nez": "Martínez", r"M{\'e}lanie": "Mélanie", r"Rub{\'e}n": "Rubén",
    r"Rom{\'a}n": "Román", r"S{\'a}nchez": "Sánchez", r"Sebasti{\'a}n": "Sebastián",
    r"Fr{\'e}d{\'e}ric": "Frédéric", r"Michi": "Michi", r"K{\'\i}ro{\u{g}}lu}": "Kıroğlu",
    # Circumflex
    r"{\^a}": "â", r"{\^e}": "ê", r"{\^i}": "î", r"{\^o}": "ô", r"{\^u}": "û",
    r"{\^A}": "Â", r"{\^E}": "Ê", r"{\^I}": "Î", r"{\^O}": "Ô", r"{\^U}": "Û",
    r"St{\'e}phane": "Stéphane", r"Fran{\c{c}}ois": "François", r"Vojt{\v{e}}ch": "Vojtěch",
    r"F{\"o}rster": "Förster", r"Baub{\"o}ck": "Bauböck", r"H{\"o}nig": "Hönig",
    r"Sch{\"o}del": "Schödel", r"L{\"u}ck": "Lück", r"R{\"u}diger": "Rüdiger",
    r"G{\"u}del": "Güdel", r"Eigm{\"u}ller": "Eigmüller", r"G{\"u}nther": "Günther",
    r"H{\'e}brard": "Hébrard", r"K{\"u}chler": "Küchler", r"L{\"a}mmerzahl": "Lämmerzahl",
    r"M{\'e}nard": "Ménard", r"{\"U}nl{\"u}t{\"u}rk}": "Ünlütürk",
    r"Gy. M.": "Gy. M.", r"J.-C.": "J.-C.", r"M.-J.": "M.-J.",
    r"{\v{S}}": "Š", r"{\v{s}}": "š", r"{\v{C}}": "Č", r"{\v{c}}": "č", r"{\v{Z}}": "Ž", r"{\v{z}}": "ž",
    # Umlaut/Dieresis
    r'{\"a}': "ä", r'{\"e}': "ë", r'{\"i}': "ï", r'{\"o}": "ö", r'{\"u}': "ü",
    r'{\"A}': "Ä", r'{\"E}': "Ë", r'{\"I}': "Ï", r'{\"O}": "Ö", r'{\"U}': "Ü",
    r'Chru{\'s}li{\'n}ska': 'Chruślińska', r'Du{\c{t}}an': 'Duțan', r'R{\"o}pke': 'Röpke',
    r'G{\"u}nther': 'Günther', r'H{\'e}brard': 'Hébrard', r'L{\'e}na': 'Léna',
    r'Lapeyr{\`e}re': 'Lapeyrère', r'Defr{\`e}re': 'Defrère', r'Cl{\'e}net': 'Clénet',
    r'Hei{\ss}el': 'Heißel', r'Baub{\"o}ck': 'Bauböck', r'F{\"o}rster': 'Förster',
    r'M{\"u}ller-Ebhardt': 'Müller-Ebhardt', r'R{\"u}diger': 'Rüdiger',
    r'L{\"u}ck': 'Lück', r'Sch{\"u}tze': 'Schütze',
    # Tilde
    r"{\~n}": "ñ", r"{\~N}": "Ñ", r"{\~a}": "ã", r"{\~o}": "õ", r"{\~A}": "Ã", r"{\~O}": "Õ",
    r"Larra{\~n}aga": "Larrañaga", r"Cond{\'e}s-Bre{\~n}a": "Condés-Breña",
    # Cedilla
    r"{\c c}": "ç", r"{\c C}": "Ç", r"{\c{s}}": "ş", r"Fran{\c{c}}ois": "François",
    r"Chru{\'s}li{\'n}ska": "Chruślińska", r"Garc{\'\i}a": "García",
    # Caron
    r"{\v{S}}": "Š", r"{\v{s}}": "š", r"{\v{C}}": "Č", r"{\v{c}}": "č", r"{\v{Z}}": "Ž", r"{\v{z}}": "ž",
    # Breve
    r"{\u{g}}": "ğ", r"{\u g}": "ğ", r"{\u{G}}": "Ğ", r"K{\i}ro{\u{g}}lu}": "Kıroğlu",
    # Turkish
    r"{\i}": "ı", r"{\.I}": "İ",
    # Other
    r"{\ss}": "ß",
    r"{\o}": "ø", r"{\O}": "Ø",
    r"{\l}": "ł", r"{\L}": "Ł",
    r"{\.C}": "Ċ",
    r"{\textendash}": "–",
    # Specific known problematic names
    r'{K{\"A}{\ensuremath{\pm}}ro{\"A}Ÿlu}': 'Kıroğlu',
    r"N{\o}r{a}": "Nora", r"Cond{\'e}s-Bre{\~n}a": "Condés-Breña",
    r"Nu{\~n}ez": "Nuñez", r"Garc{\'\i}a": "García", r"Mar{\'\i}a": "María",
    r"Larra{\~n}aga": "Larrañaga", r"Ni{\~n}o": "Niño", r"Vilchez": "Vilchez",
    r"Dani{\`e}le": "Danièle", r"V{\'a}zquez-Aceves": "Vázquez-Aceves",
    r"Bogdanovi{\'c}": "Bogdanović", r"Bl{\'a}zquez-Salcedo": "Blázquez-Salcedo",
    r"Bo{\v{s}}kovi{\'c}": "Bošković", r"Br{\"u}gmann": "Brügmann",
    r"Cerd{\'a}-Dur{\'a}n": "Cerdá-Durán", r"Chru{\'s}ciel": "Chruściel",
    r"Comp{\`e}re": "Compère", r"Cordero-Carri{\'o}n": "Cordero-Carrión",
    r"Gal'tsov": "Gal'tsov", r"Garc{\'\i}a-Bellido": "García-Bellido",
    r"Gua{\~n}una": "Guañuna", r"Jantzen": "Jantzen",
    r"L{\"a}mmerzahl": "Lämmerzahl", r"Jos{\'e}": "José",
    r"Racz": "Racz", r"Ramazano{\u{g}}lu}": "Ramazanoğlu",
    r"Sanchis-Gual": "Sanchis-Gual", r"Torres-Forn{\'e}": "Torres-Forné",
    r"Tsygankov": "Tsygankov", r"Urena-L{\'o}pez": "Urena-López",
    r"K{\i}van{\c{c}}": "Kıvanç", r"{\.I}": "İ", r"Maureira-Fredes": "Maureira-Fredes",
    r"Cristi{\'a}n": "Cristián", r"Sch{\"o}del": "Schödel", r"Baumg{\k{a}}rdt": "Baumgardt",
    r"Gallego-Cano": "Gallego-Cano", r"Gallego-Calvente": "Gallego-Calvente",
    r"Nogueras-Lara": "Nogueras-Lara", r"V{\'a}zquez-Aceves": "Vázquez-Aceves",
    r"Zaja{\v{c}}ek": "Zajaček", r"M{\'e}lanie": "Mélanie", r"J.~M. Diederik": "J. M. Diederik",
    r"Rub{\'e}n": "Rubén", r"Luc{\'\i}a": "Lucía", r"Gonz{\'a}alez": "González",
    r"Kontstantina": "Kontstantina", r"Mar{\'\i}n": "Marín", r"Garc{\'\i}a": "García",
    r"Abhimat K.": "Abhimat K.", r"Gualandris": "Gualandris",
    r"Giuseppe": "Giuseppe", r"Mart{\'\i}nez": "Martínez",
    r"{\'A}lvaro": "Álvaro", r"Mastrobuono-Battisti": "Mastrobuono-Battisti",
    r"Francisco": "Francisco", r"Govind": "Govind", r"Rom{\'a}n": "Román",
    r"Nils": "Nils", r"Nadeen": "Nadeen", r"S{\'a}nchez": "Sánchez",
    r"Berm{\'u}dez": "Bermúdez", r"Monge": "Monge", r"{\'A}lvaro": "Álvaro",
    r"Mathias": "Mathias", r"Mattia C.": "Mattia C.", r"Jonathan C.": "Jonathan C.",
    r"Brian": "Brian", r"Robin": "Robin", r"Hideki": "Hideki",
    r"Elena": "Elena", r"Roeland": "Roeland", r"Sill": "Sill",
    r"Pierre": "Pierre", r"Sebastiano": "Sebastiano", r"Daniel": "Daniel",
    r"Gunther": "Gunther", r"Siyao": "Siyao", r"Taihei": "Taihei",
    r"Farhad": "Farhad", r"Michal": "Michal", r"Manuela": "Manuela",
    r"St{\'e}phane": "Stéphane", r"Du{\c{t}}an": "Duțan",
    r"Tom{\'a}s": "Tomás", r"R{\"o}pke": "Röpke",
    r"V{\'a}zquez-Aceves": "Vázquez-Aceves", r"Sopuerta": "Sopuerta",
    r"Zolt{\'a}n": "Zoltán", r"Bogdanovi{\'c}": "Bogdanović",
    r"Fran{\c{c}}ois": "François", r"Ak{\c{c}}ay": "Akçay", r"Josu C.": "Josu C.",
    r"B{\'e}atrice": "Béatrice", r"Buonanno": "Buonanno",
    r"C{\'a}rdenas-Avenda{\~n}o": "Cárdenas-Avendaño", r"Garc{\'\i}a-Bellido": "García-Bellido",
    r"Gracia-Linares": "Gracia-Linares", r"K{\"u}chler": "Küchler",
    r"Fran{\c{c}}ois": "François", r"Lovelace": "Lovelace",
    r"Lukes-Gerakopoulos": "Lukes-Gerakopoulos", r"Charalampos": "Charalampos",
    r"Nov{\'a}k": "Novák", r"R{\"u}ter": "Rüter", r"Zilh{\~a}o": "Zilhão",
    r"Giacomazzo": "Giacomazzo", r"Gupta": "Gupta", r"Han": "Han",
    r"Husa": "Husa", r"Jetzer": "Jetzer", r"Kocsis": "Kocsis",
    r"L{\"a}mmerzahl": "Lämmerzahl", r"Lemos": "Lemos", r"Macedo": "Macedo",
    r"Pappas": "Pappas", r"Paschalidis": "Paschalidis", r"Pfeiffer": "Pfeiffer",
    r"R{\"u}ter": "Rüter", r"Sagunski": "Sagunski", r"Skoup{\'y}": "Skoupý",
    r"Sperhake": "Sperhake", r"Sopuerta": "Sopuerta", r"Va{\~n}{\'o}-Vi{\~n}uales": "Vaño-Viñuales",
    r"Gair": "Gair", r"Haas": "Haas", r"Hirschmann": "Hirschmann",
    r"Huerta": "Huerta", r"Khalil": "Khalil", r"Lewis": "Lewis",
    r"Nardini": "Nardini", r"Ottewill": "Ottewill", r"Pantelidou": "Pantelidou",
    r"Piovano": "Piovano", r"Redondo-Yuste": "Redondo-Yuste", r"Sagunski": "Sagunski",
    r"Stein": "Stein", r"Skoup{\'y}": "Skoupý", r"Sperhake": "Sperhake",
    r"Speri": "Speri", r"Spieksma": "Spieksma", r"Stevens": "Stevens",
    r"Trestini": "Trestini", r"Va{\~n}{\'o}-Vi{\~n}uales": "Vaño-Viñuales"
}


# --- Functions ---

def process_author_match(match):
    """
    Callback function for re.sub to process author fields.
    Removes all inner curly braces.
    """
    # group(1) = "author = {"
    # group(2) = content
    # group(3) = "}," or "}" (including newlines)
    content = match.group(2)
    processed_content = content.replace('{', '').replace('}', '')
    return f'{match.group(1)}{processed_content}{match.group(3)}'

def main(input_file):
    """
    Main function to read, process, and print the BibTeX file.
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File not found: {input_file}", file=sys.stderr)
        sys.exit(1) # Exit with an error code
    except Exception as e:
        print(f"Error reading file '{input_file}': {e}", file=sys.stderr)
        sys.exit(1) # Exit with an error code

    # 1. Apply journal replacements (safe)
    for macro, full in JOURNAL_MAP.items():
        content = content.replace(f'journal = {{{macro}}}', f'journal = {{{full}}}')

    # 2. Apply accent replacements (safe)
    # Iterate multiple times to catch nested or combined accents
    for _ in range(3):
        for tex, uni in ACCENT_MAP.items():
            content = content.replace(tex, uni)

    # 3. Apply author replacements safely
    # This pattern matches author fields ending in a comma.
    # It is NOT using re.DOTALL, so it only matches if the
    # entire field is on one line (which they are in your file).
    author_pattern_comma = re.compile(
        r'(author\s*=\s*\{)(.*?)(\},\s*\n)', re.IGNORECASE
    )
    # This pattern matches author fields that are the LAST field
    # in an entry (no comma, followed by the entry's closing brace).
    author_pattern_final = re.compile(
        r'(author\s*=\s*\{)(.*?)(\}\s*\n\s*\})', re.IGNORECASE
    )

    content = author_pattern_comma.sub(process_author_match, content)
    content = author_pattern_final.sub(process_author_match, content)

    # Output the modified content to standard output
    print(content)

# --- Execution ---

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("-----------------------------------------------------------------", file=sys.stderr)
        print("Error: No input file specified.", file=sys.stderr)
        print("Usage: python clean_bibtex_v2.py <your_input_file.bib>", file=sys.stderr)
        print("Example: python clean_bibtex_v2.py my_export.bib > cleaned.bib", file=sys.stderr)
        print("-----------------------------------------------------------------", file=sys.stderr)
        # Print the help text (the docstring) if no argument is given
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    
    input_filename = sys.argv[1]
    main(input_filename)
