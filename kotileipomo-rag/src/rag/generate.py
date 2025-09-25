from __future__ import annotations

from typing import List, Tuple, Optional

from .ingest import Doc
from .tokenize import tokens, normalize


def _lang_code(lang: str | None) -> str:
    ln = (lang or "fi").lower()
    if ln not in {"fi", "en", "sv"}:
        return "fi"
    return ln


def _contains(text: str, needles: List[str]) -> bool:
    return any(n in text for n in needles)


def _order_ui_block(lang: str) -> str:
    url = "https://rakaskotileipomo.fi/verkkokauppa"
    if lang == "en":
        title = "Order Online"
        sub = "Pickup in store, pay at pickup."
        btn = "Open Online Shop"
        chat = "Order in chat"
    elif lang == "sv":
        title = "Beställ i webbutiken"
        sub = "Avhämtning i butiken, betalning på plats."
        btn = "Öppna webbutiken"
        chat = "Beställ i chatten"
    else:
        title = "Tilaa verkkokaupasta"
        sub = "Nouto myymälästä, maksu paikan päällä."
        btn = "Avaa verkkokauppa"
        chat = "Tilaa chatissa"
    return (
        '<div class="order-ui">\n'
        f'  <div class="order-title">{title}</div>\n'
        f'  <div class="order-sub">{sub}</div>\n'
        '  <div class="order-buttons">\n'
        f'    <a class="btn" href="{url}" target="_blank" rel="noopener">{btn}</a>\n'
        f'    <button class="btn" data-action="start-order">{chat}</button>\n'
        '  </div>\n'
        '</div>'
    )


def _order_with_note(note: str, lang: str) -> str:
    return f"<p>{note}</p>{_order_ui_block(lang)}"


def _suggest_menu_block(lang: str) -> str:
    title = {
        "en": "Would you like to see the menu?",
        "sv": "Vill du se menyn?",
        "fi": "Haluatko nähdä valikon?",
    }[lang]
    label = {
        "en": "Show menu",
        "sv": "Visa menyn",
        "fi": "Näytä valikko",
    }[lang]
    payload = {
        "en": "Show me the menu",
        "sv": "Visa menyn",
        "fi": "Näytä valikko",
    }[lang]
    return (
        '<div class="suggest">'
        f'<div class="suggest-title">{title}</div>'
        f'<a class="btn suggest-btn" data-suggest="{payload}">{label}</a>'
        '</div>'
    )


def _frozen_response(lang: str) -> str:
    text = {
        "fi": "Myymme myös raakapakasteita, jotka voit paistaa kotona. Löydät vaihtoehdot valikostamme.",
        "en": "We also sell par-baked frozen items that you can finish at home. You’ll find them in our menu.",
        "sv": "Vi säljer också råfrysta bakverk som du kan grädda hemma. Du hittar dem i vår meny.",
    }[lang]
    return f"<p>{text}</p>{_suggest_menu_block(lang)}"


def _special_answer(query: str, lang: str) -> Optional[str]:
    ln = _lang_code(lang)
    qn = normalize(query)
    words = [w for w in qn.split() if w]
    greet_terms = {
        "hei","moi","moikka","morjes","moro","terve","heippa",
        "hi","hello","hey","hola","ciao"
    }
    if words and len(words) <= 4 and all(w in greet_terms for w in words):
        greetings = {
            "fi": "Hei! 👋 Kuinka voin auttaa?",
            "en": "Hi there! 👋 How can I help today?",
            "sv": "Hej! 👋 Hur kan jag hjälpa till?",
        }
        return greetings.get(ln, greetings["fi"])

    weekday_tokens = {
        "mon": {"maanant", "monday"},
        "tue": {"tiist", "tuesday"},
        "wed": {"keskiviik", "keskiv", "wednes"},
        "thu": {"torst", "thursday"},
        "fri": {"perjant", "friday"},
        "sat": {"lauant", "saturday"},
    }

    def _mentioned(keys: set[str]) -> bool:
        return any(any(tok in qn for tok in weekday_tokens[k]) for k in keys)

    if _mentioned({"mon"}) and any(k in qn for k in ["auki", "open", "avoin", "avataan", "auke", "milloin", "mihin aikaan", "kello", "time"]):
        texts = {
            "fi": (
                "Maanantaisin myymälä on suljettu. Olemme avoinna torstaisin ja perjantaisin klo 11–17 sekä lauantaisin klo 11–15."
                " Jos haluat noudon maanantaille, sovi asiasta etukäteen sähköpostitse (rakaskotileipomo@gmail.com), niin katsomme onnistuuko järjestely."
            ),
            "en": (
                "We’re closed on Mondays. Our regular opening hours are Thu–Fri 11:00–17:00 and Sat 11:00–15:00."
                " If you need a Monday pickup, email us first (rakaskotileipomo@gmail.com) so we can confirm whether it’s possible."
            ),
            "sv": (
                "Vi har stängt på måndagar. Ordinarie öppettider är tors–fre kl. 11–17 och lör kl. 11–15."
                " Behöver du hämta på måndag? Mejla oss först (rakaskotileipomo@gmail.com) så ser vi om det går att ordna."
            ),
        }
        return texts[ln]

    if _mentioned({"tue"}) and any(k in qn for k in ["auki", "open", "avataan", "auke", "mihin aikaan", "milloin", "kello", "time"]):
        texts = {
            "fi": "Tiistaisin varsinainen myymälä on suljettu, mutta ennakkonoudot onnistuvat sopimalla etukäteen sähköpostitse osoitteeseen rakaskotileipomo@gmail.com. Varsinaiset aukiolot ovat to–pe klo 11–17 ja la klo 11–15.",
            "en": "We’re not open to walk-ins on Tuesdays; pickups require arranging in advance via email (rakaskotileipomo@gmail.com). Regular opening hours are Thu–Fri 11:00–17:00 and Sat 11:00–15:00.",
            "sv": "Vi håller inte öppet för drop-in på tisdagar; avhämtning kräver överenskommelse via mejl (rakaskotileipomo@gmail.com). Ordinarie öppettider är tors–fre kl. 11–17 och lör kl. 11–15.",
        }
        return texts[ln]

    if _mentioned({"wed"}) and any(k in qn for k in ["auki", "open", "avataan", "auke", "mihin aikaan", "milloin", "kello", "time"]):
        texts = {
            "fi": "Keskiviikkoisin myymälä on kiinni, mutta ennakkonoudot onnistuvat sopimalla etukäteen sähköpostitse (rakaskotileipomo@gmail.com). Varsinaiset aukiolot ovat to–pe klo 11–17 ja la klo 11–15.",
            "en": "We’re closed on Wednesdays, but you can arrange a pickup in advance by emailing rakaskotileipomo@gmail.com. Regular hours are Thu–Fri 11:00–17:00 and Sat 11:00–15:00.",
            "sv": "På onsdagar har vi stängt, men förhandsbokade avhämtningar går att ordna via mejl till rakaskotileipomo@gmail.com. Ordinarie öppettider är tors–fre kl. 11–17 och lör kl. 11–15.",
        }
        return texts[ln]

    no_arrangement_terms = {
        "ilman ennakkosop", "ilman sopim", "ilman soppar", "ilman että", "ilman etukäteist", "ilman etukäteen",
        "ilman yhteyttä", "ilman kontaktia", "ilman email", "ilman sähköpostia",
        "without prior", "without agreement", "without arrangement", "without contacting", "without emailing", "without email",
        "without reaching out", "without contact", "without notice",
        "utan att kontakta", "utan att höra av", "utan att meddela", "utan att mejla", "utan att maila", "utan kontakt",
        "ei sopimusta", "ei yhteydenottoa"
    }
    pickup_terms = {
        "nout", "nouto", "noutoon", "nouton", "nouta", "noud", "noudon", "nouda", "noutais", "noutaisin",
        "pickup", "pick up", "collect", "collection", "hakemaan", "hakua", "haen", "haetta"
    }

    if _contains(qn, list(no_arrangement_terms)) and _contains(qn, list(pickup_terms)):
        texts = {
            "fi": "Nouto aukioloaikojen ulkopuolella edellyttää ennakkosopimusta. Ota yhteyttä sähköpostitse rakaskotileipomo@gmail.com, niin vahvistamme mahdollisen ajan ja järjestelyt.",
            "en": "Pickups outside normal opening hours need to be agreed in advance. Please email us at rakaskotileipomo@gmail.com so we can confirm the timing and details.",
            "sv": "Avhämtning utanför ordinarie öppettider måste avtalas i förväg. Mejla oss på rakaskotileipomo@gmail.com så bekräftar vi tid och arrangemang.",
        }
        return texts[ln]

    import re as _re
    orig = (query or "").lower()
    hours = []
    for pat in [r"(?:klo|kello)\s*(\d{1,2})", r"\b(\d{1,2})\s*(?:pm|p\.m\.)"]:
        hours.extend(int(h) for h in _re.findall(pat, orig))
    if not hours:
        colon_matches = _re.findall(r"\b(\d{1,2})\s*:\s*(\d{2})", orig)
        hours.extend(int(hh) for hh, _ in colon_matches)
    if hours and _contains(qn, list(pickup_terms)):
        def requires_arrangement(hour: int) -> bool:
            if hour >= 18 or hour < 8:
                return True
            if _mentioned({"sat"}):
                return hour > 15
            return hour > 17
        if any(requires_arrangement(h) for h in hours):
            texts = {
                "fi": "Aukioloaikojen ulkopuoliset noudot tulee sopia etukäteen. Lähetä meille sähköpostia osoitteeseen rakaskotileipomo@gmail.com, niin vahvistamme ajan.",
                "en": "Pickups outside normal opening hours need an email agreement first. Please write to rakaskotileipomo@gmail.com so we can confirm a time.",
                "sv": "Avhämtningar utanför ordinarie tider måste avtalas i förväg. Mejla oss på rakaskotileipomo@gmail.com så bekräftar vi tiden.",
            }
            return texts[ln]

    if _contains(qn, ["karjalanpiir", "karelian", "karelsk"]) and _contains(qn, ["täyte", "täytt", "filling", "fyllning", "fyllningar"]):
        texts = {
            "fi": "Karjalanpiirakoissamme on neljä vakituista täytettä: riisipuuro, perunasose, ohrapuuro ja vegaaninen riisipuuro (ilman maitotuotteita).",
            "en": "We bake our Karelian pies with four fillings: rice porridge, mashed potato, barley porridge and a vegan rice porridge made without dairy.",
            "sv": "Våra karelska piroger finns med fyra fyllningar: risgrynsgröt, potatismos, korngröt och en vegansk risgröt utan mejeriprodukter.",
        }
        return texts[ln]

    if _contains(qn, ["karjalanpiir", "karelian", "karelsk"]) and _contains(qn, ["laktoos", "lactose", "laktos", "maito", "milk", "mjölk", "dairy"]):
        texts = {
            "fi": "Karjalanpiirakoiden riisipuuro tehdään laktoosittomasta maidosta, joten ne ovat laktoosittomia mutta sisältävät maitotuotteen.",
            "en": "Our Karelian pies use lactose-free milk in the rice porridge, so they are lactose-free but do contain dairy.",
            "sv": "Vi kokar risgröten till Karelska piroger med laktosfri mjölk – pirogerna är laktosfria men innehåller mejeriprodukt.",
        }
        return texts[ln]

    if _contains(qn, ["laktoos", "lactose", "laktos"]):
        texts = {
            "fi": "Kyllä, kaikki tuotteemme ovat laktoosittomia, joten laktoosiherkkä voi nauttia niistä huoletta.",
            "en": "Yes—every product we bake is lactose-free, so you can enjoy them even with lactose intolerance.",
            "sv": "Ja, alla våra produkter är laktosfria så du kan njuta av dem även om du undviker laktos.",
        }
        return texts[ln]

    if _contains(qn, ["gluteen", "gluten"]):
        texts = {
            "fi": "Meillä ei ole valitettavasti gluteenittomia tuotteita. Tilamme eivät sovellu gluteenittomaan leivontaan muun leivonnan ohella jauhopölyn vuoksi.",
            "en": "Unfortunately we do not offer gluten-free products. Our bakery handles plenty of wheat and rye flour so we can’t guarantee a gluten-free environment.",
            "sv": "Tyvärr erbjuder vi inga glutenfria produkter. Bageriet hanterar vetemjöl och rågmjöl, så miljön är inte glutenfri.",
        }
        return texts[ln]

    if _contains(qn, ["etukäteen", "ennakk", "preorder", "pre-order", "pre order", "förbeställ", "förbeställning"]) and not _contains(qn, ["ennakkomaks", "jono", "jonot", "jonon"]):
        return _order_ui_block(ln)

    if _contains(qn, ["verkkokaup", "nettisivu", "online shop", "online store", "webbutik", "webbshop", "shop online"]):
        notes = {
            "fi": "Tee tilaus verkkokaupassa, niin voimme vahvistaa sen heti—nouda myymälästä aukioloaikoina (emme tee toimituksia).",
            "en": "Place your order in the online shop and we’ll confirm it right away—pickup in store during opening hours (we don’t deliver).",
            "sv": "Lägg din beställning i webbutiken så bekräftar vi den direkt—hämta i butiken under öppettiderna (vi erbjuder ingen leverans).",
        }
        return _order_with_note(notes[ln], ln)

    order_terms = {
        "tilaus", "tilauk", "tilata", "tilausta", "tilaaminen", "orders", "order", "beställ", "beställning", "beställningar"
    }
    if _contains(qn, list(order_terms)) and not any(k in qn for k in [
        "peru", "muuta", "muok", "ennakkomaks", "delivery", "toimitus", "post" , "breakfast", "aamupala", "iltapala",
        "lasku", "invoice", "yrityk", "business"
    ]):
        return _order_ui_block(ln)

    if _contains(qn, ["yritys", "yritykselle", "b2b"]) and not _contains(qn, ["lasku", "invoice"]):
        notes = {
            "fi": "Yritysasiakkaat voivat tehdä suurempia tilauksia sähköpostitse rakaskotileipomo@gmail.com. Varaathan 2–3 päivää aikaa tuotantoa varten ja muistathan, että nouto tapahtuu myymälästämme.",
            "en": "Business customers can place larger orders by emailing rakaskotileipomo@gmail.com. Please allow 2–3 days for production; pickups are always from our shop.",
            "sv": "Företagskunder kan lägga större beställningar via e-post till rakaskotileipomo@gmail.com. Räkna med 2–3 dagar för bakningen och hämta beställningen i butiken.",
        }
        return _order_with_note(notes[ln], ln)

    if "perunahiut" in qn:
        texts = {
            "fi": "Käytämme lisäaineettomia perunahiutaleita – täyte sekoitetaan leipomolla ilman valmista soseita.",
            "en": "We use additive-free potato flakes; the filling is mixed on site without ready-made mash.",
            "sv": "Vi använder tillsatsfria potatisflingor – fyllningen blandas i bageriet utan färdig mos.",
        }
        return texts[ln]

    if "perunapiir" in qn:
        texts = {
            "fi": "Kyllä, perunatäytteinen karjalanpiirakka kuuluu vakituiseen valikoimaamme. Saat sen uunituoreena myymälästä sekä raakapakasteena kotiin paistettavaksi.",
            "en": "Yes, potato-filled Karelian pies are part of our regular range. You can buy them fresh from the shop or as par-baked frozen pies for home baking.",
            "sv": "Ja, potatisfyllda karelska piroger ingår i vårt fasta sortiment. De finns både nygräddade i butiken och som råfrysta för hemmagräddning.",
        }
        return texts[ln]

    if "ohrapiir" in qn:
        texts = {
            "fi": "Ohrapiirakka on yksi vakiosmakumme. Piirakat ovat laktoosittomia ja saatavana sekä tuoreina että raakapakasteina.",
            "en": "Barley-filled Karelian pies are one of our core flavours. They’re lactose-free and available fresh or as frozen bake-at-home packs.",
            "sv": "Kornpiroger är en av våra fasta smaker. De är laktosfria och finns både nygräddade och råfrysta för hemmagräddning.",
        }
        return texts[ln]

    if _contains(qn, ["riisipiir", "piirak"]) and _contains(qn, ["vegaan", "maidot", "kauramaid", "vegaani", "vegg"]):
        texts = {
            "fi": "Leivomme sekä perinteistä riisipiirakkaa että vegaanista riisipiirakkaa, jonka puuro tehdään kauramaidolla. Vegaaniversio kannattaa tilata etukäteen, jotta varmistamme saatavuuden.",
            "en": "We bake both the classic rice pie and a vegan rice pie whose porridge base is made with oat milk. Please preorder the vegan batch so we can guarantee availability.",
            "sv": "Vi bakar både den klassiska rispirogen och en vegansk variant där gröten görs med havremjölk. Förboka gärna den veganska satsen så vi kan garantera tillgången.",
        }
        return texts[ln]

    if "pull" in qn:
        texts = {
            "fi": "Kyllä, vitriinissä on päivittäin suomalaisia pullia kuten kaneli- ja voisilmäpullia sekä sesongin erikoisuuksia. Kardemumman jauhamme itse kokonaisista siemenistä.",
            "en": "Yes, we bake Finnish buns daily – cinnamon rolls, butter-eye buns and seasonal specials. We grind the cardamom fresh from whole pods.",
            "sv": "Ja, vi har färska finska bullar varje dag – kanelbullar, smöröga-bullar och säsongens specialiteter. Kardemumman mals alltid färsk.",
        }
        return texts[ln]

    if _contains(qn, ["pähkin", "pahkin", "nut"]):
        texts = {
            "fi": "Emme käytä pähkinöitä vakituisten tuotteiden valmistuksessa. Runebergin torttu sisältää mantelijauhetta, ja se leivotaan erillään muista tuotteista.",
            "en": "We don’t use nuts in our regular products. Runeberg torte does contain almond, and we bake it separately from the other items.",
            "sv": "Vi använder inte nötter i vårt ordinarie sortiment. Runebergstårta innehåller mandel och bakas separat från övriga produkter.",
        }
        return texts[ln]

    if _contains(qn, ["voita", "butter"]) and _contains(qn, ["pull", "bun"]):
        texts = {
            "fi": "Pullataikinassa käytämme suomalaista voita – emme käytä margariinia.",
            "en": "We use Finnish butter in our bun dough—no margarine.",
            "sv": "Vi använder finskt smör i bulldegen – ingen margarin.",
        }
        return texts[ln]

    if _contains(qn, ["vegaan", "maidoton"]) and _contains(qn, ["kanelipulla", "korvapuusti", "cinnamon"]):
        texts = {
            "fi": "Perinteinen kanelipulla sisältää voita ja kananmunavoitelun, joten se ei ole vegaaninen. Tarvitessasi voimme leipoa erän vegaanisia pullia ennakkotilauksesta.",
            "en": "Our classic cinnamon bun uses butter and an egg wash, so it isn’t vegan. Let us know in advance and we can bake a vegan batch to order.",
            "sv": "Den klassiska kanelbullen innehåller smör och penslas med ägg, så den är inte vegansk. Med förbeställning kan vi baka en vegansk sats.",
        }
        return texts[ln]

    if _contains(qn, ["korvapuusti", "korvapuust", "cinnamon roll"]) and _contains(qn, ["myyt", "sale"]):
        texts = {
            "fi": "Kyllä – korvapuusti on vitriinimme vakkariherkku.",
            "en": "Yes, cinnamon rolls (korvapuusti) are a staple in our display.",
            "sv": "Ja, korvapuusti (kanelbulle) finns nästan alltid i montern.",
        }
        return texts[ln]

    if _contains(qn, ["erikoispull", "specialbulla", "sesonki"]):
        texts = {
            "fi": "Sesongeittain tarjoamme erikoispullia, esim. Runebergin torttuja tai laskiaispullia – seuraa somea ja verkkokauppaa.",
            "en": "We rotate seasonal buns—think Runeberg tortes, Shrove buns and other specials. Follow our social channels for updates.",
            "sv": "Vi erbjuder säsongsbullar, till exempel Runebergstårtor och fastlagsbullar. Följ våra kanaler för nyheter.",
        }
        return texts[ln]

    if _contains(qn, ["kuinka iso", "paljonko pain", "size"]) and _contains(qn, ["pull", "bun"]):
        texts = {
            "fi": "Pullat ovat runsaita – noin 110–120 grammaa kappale, suunnilleen kämmenen kokoisia.",
            "en": "Each bun is generous, roughly 110–120 g (about the size of your palm).",
            "sv": "Bullarna är rejält tilltagna – cirka 110–120 g styck, ungefär handflatsstora.",
        }
        return texts[ln]

    if _contains(qn, ["kananmun", "egg"]) and _contains(qn, ["pull", "bun"]):
        texts = {
            "fi": "Pullien pinta kaunistellaan ohuella kananmunavoitelulla ennen paistoa. Ennakkotilauksessa voimme jättää voitelun pois.",
            "en": "We brush the buns with a light egg wash before baking; for preorders we can skip it on request.",
            "sv": "Bullarna penslas lätt med ägg före gräddning – vid förbeställning kan vi hoppa över penslingen om du vill.",
        }
        return texts[ln]

    if _contains(qn, ["sokeri", "kuorrute", "icing"]) and _contains(qn, ["pull", "bun"]):
        texts = {
            "fi": "Vakio kaneli- ja voisilmäpullamme eivät sisällä sokerikuorrutetta; erikoispullissa saattaa olla kuorrutus.",
            "en": "Our regular cinnamon and butter-eye buns don’t have icing—seasonal specials may.",
            "sv": "Våra vanliga kanel- och smörögebullar har ingen glasyr – men säsongsbullar kan ha det.",
        }
        return texts[ln]

    if _contains(qn, ["pull", "bun"]) and _contains(qn, ["kauan", "kuinka", "säily"]):
        texts = {
            "fi": "Pullat ovat parhaimmillaan samana päivänä. Ne säilyvät huoneenlämmössä 1–2 päivää tai pidempään pakastettuna.",
            "en": "Buns are best the day they’re baked. Keep them 1–2 days at room temperature or freeze for longer storage.",
            "sv": "Bullarna är bäst samma dag. De håller 1–2 dagar i rumstemperatur eller längre i frysen.",
        }
        return texts[ln]

    if _contains(qn, ["kakku", "cake"]) and _contains(qn, ["tilaus", "tilauk", "tilaust", "custom", "hää", "catering"]):
        texts = {
            "fi": "Emme leivo kakkuja (täytekakkuja, kuivakakkuja), voileipäkakkuja, lihapiirakoita tai konditoriatuotteita. Olemme ensisijaisesti karjalanpiirakkaleipomo.",
            "en": "We do not bake cakes (layer cakes, loaf cakes), sandwich cakes, meat pies or confectionery items. We’re primarily a Karelian pie bakery.",
            "sv": "Vi bakar inte tårtor (gräddtårtor eller mjuka kakor), smörgåstårtor, köttpiroger eller konditorivaror. Vi är i första hand ett karelskt pirogbageri.",
        }
        return texts[ln]

    if _contains(qn, ["pysäkö", "park", "parkering"]):
        texts = {
            "fi": "Kadunvarsipysäköinti Kumpulantiellä ja lähikaduilla on maksullista arkipäivisin – käytä pysäköintisovellusta tai automaattia.",
            "en": "There’s paid street parking on Kumpulantie and the surrounding streets—use the local parking app or meter.",
            "sv": "Det finns avgiftsbelagd gatuparkering på Kumpulantie och närliggande gator – använd parkeringsappen eller automaten.",
        }
        return texts[ln]

    if _contains(qn, ["julkis", "tram", "metro", "bus", "bussi", "spårvagn", "raitiovaunu", "pysäk", "pysak"]) and not _contains(qn, ["y-tunnus", "ytunnus", "y tunnus", "y id", "business id", "company id", "företagsnummer"]):
        texts = {
            "fi": "Lähimmät pysäkit ovat Mäkelänrinne (bussit 55, 59 ja useita muita linjoja sekä raitiovaunut 1 ja 7) ja Jämsänkatu (raitiovaunu 9 ja bussi 59). Molemmista on parin minuutin kävely leipomolle. Tarkista ajantasaiset reitit osoitteesta hsl.fi.",
            "en": "The closest stops are Mäkelänrinne—served by buses 55, 59 and numerous other lines plus trams 1 and 7—and Jämsänkatu for tram 9 and bus 59. Both are roughly a two-minute walk away. Please see hsl.fi for current routes.",
            "sv": "Närmaste hållplatser är Mäkelänrinne (bussarna 55, 59 och flera andra linjer samt spårvagn 1 och 7) och Jämsänkatu där spårvagn 9 och buss 59 stannar. Båda ligger cirka två minuters promenad bort. Se hsl.fi för uppdaterade rutter.",
        }
        return texts[ln]

    if _contains(qn, ["esteet", "accessible", "tillgänglig"]):
        texts = {
            "fi": "Sisäänkäynnille johtaa kolme porrasta eikä rampia ole. Autamme mielellämme kantamalla tilauksesi sisään tai ulos.",
            "en": "There are three steps up to the entrance and no ramp. We’re happy to help carry your order in or out.",
            "sv": "Det finns tre trappsteg upp till ingången och ingen ramp. Vi hjälper gärna till att bära in eller ut din beställning.",
        }
        return texts[ln]

    if _contains(qn, ["kahvi", "coffee"]) and _contains(qn, ["saako", "offer", "serv"]):
        texts = {
            "fi": "Myymälässämme ei ole kahvitarjoilua – keskitymme leivonnaisiin, mutta voit tuoda oman take away -kahvisi.",
            "en": "We don’t serve coffee—we focus on the bakes, though you’re welcome to bring your own take-away coffee.",
            "sv": "Vi serverar inte kaffe – vi fokuserar på bakverken, men ta gärna med eget take away-kaffe.",
        }
        return texts[ln]

    if _contains(qn, ["ruokapaik", "lähist", "nearby food", "restaurant"]):
        texts = {
            "fi": "Vallilan alueella on useita kahviloita ja ravintoloita – esimerkiksi Paavalinkirkon ja Konepajan kulmilla muutaman minuutin kävelymatkan päässä.",
            "en": "There are plenty of cafés and restaurants in Vallila—Paavalin kirkko and the Konepaja block are only a few minutes away on foot.",
            "sv": "Det finns gott om kaféer och restauranger i Vallila – kring Paavalinkyrkan och Konepaja bara några minuters promenad bort.",
        }
        return texts[ln]

    if (_contains(qn, ["ilman", "walk", "drop"]) and _contains(qn, ["tilaus", "tilaa", "order"])):
        texts = {
            "fi": "Voit tulla ostoksille ilman ennakkotilausta – vitriinissä on tuotteita niin kauan kuin paistoerää riittää.",
            "en": "Yes, walk-ins are welcome—we keep the display stocked while each bake lasts.",
            "sv": "Ja, drop-in fungerar fint – montern fylls på så länge varje bakning räcker.",
        }
        return texts[ln]

    if _contains(qn, ["tarjoilu", "vat", "vati", "patar", "serving", "platter", "astiat", "cutlery", "dish", "lautanen", "plate"]) and _contains(qn, ["lain", "vuokra", "rent", "varata", "reserve"]):
        texts = {
            "fi": "Emme tarjoa tarjoiluvateja, astioita tai aterimia lainattavaksi – tuotteet pakataan mukaan kertakäyttö- tai kierrätyspakkauksiin.",
            "en": "We don’t rent serving platters, dishes or cutlery; everything is packed to-go in our own packaging.",
            "sv": "Vi hyr inte ut serveringsfat, kärl eller bestick – allt packas för avhämtning i våra egna förpackningar.",
        }
        return texts[ln]

    if _contains(qn, ["työpor", "tyopor", "tiim", "team", "staff"]) and _contains(qn, ["aamupala", "iltapala", "breakfast", "evening snack", "snack"] ) and _contains(qn, ["tilaus", "tilata", "order"]):
        texts = {
            "fi": (
                "Kyllä, tilaukset voi noutaa myymälästämme aukioloaikoina. Suuremmat erät onnistuvat myös maanantaisin, tiistaisin ja keskiviikkoisin sopimalla etukäteen."
            ),
            "en": (
                "Yes, you can pick up from the shop during opening hours. Larger batches can also be prepared for Monday, Tuesday or Wednesday pickups when arranged in advance."
            ),
            "sv": (
                "Ja, du kan hämta beställningen under öppettiderna. Större satser ordnar vi även för måndagar, tisdagar och onsdagar om vi kommer överens i förväg."
            ),
        }
        follow = {
            "fi": "Kerro ryhmän koko ja toivottu noutoaika sähköpostilla osoitteeseen rakaskotileipomo@gmail.com, niin vahvistamme järjestelyt ja aikataulun.",
            "en": "Email us at rakaskotileipomo@gmail.com with your headcount and desired pickup time so we can confirm the plan and timing.",
            "sv": "Mejla oss på rakaskotileipomo@gmail.com med antal personer och önskad avhämtningstid så bekräftar vi upplägget och tidtabellen.",
        }
        return f"<p>{texts[ln]}</p><p>{follow[ln]}</p>"

    if _contains(qn, ["post", "posti", "postitse", "ship", "shipping", "delivery", "deliver", "toimitus", "lähett", "lähettäk", "lähettä"]) and _contains(qn, ["tuote", "tuotte", "tuotteet", "tuotteita", "tilaus", "order", "paketti", "products"]):
        paragraphs = {
            "fi": (
                "Tilaukset noudetaan myymälästämme aukioloaikoina. Suuremmat erät onnistuvat myös maanantaisin, tiistaisin ja keskiviikkoisin sopimalla etukäteen."
            ),
            "en": (
                "Orders are picked up from the shop during opening hours. Larger batches can be prepared for Monday, Tuesday or Wednesday pickups when arranged in advance."
            ),
            "sv": (
                "Beställningar hämtas i butiken under öppettiderna. Större satser kan ordnas för hämtning måndagar, tisdagar eller onsdagar efter överenskommelse."
            ),
        }
        follow = {
            "fi": "Emme valitettavasti tarjoa kotiinkuljetusta, mutta voit tilata taksin tai kuljetuspalvelun hakemaan tilauksen. Luovutamme tuotteet kuljettajalle ja lähetämme tarvittaessa maksulinkin etukäteen, kun tilaus on vahvistettu.",
            "en": "We do not offer delivery, but you can arrange a taxi or courier to collect the order. We hand everything over to the driver and can send a payment link in advance once the order is confirmed.",
            "sv": "Vi erbjuder ingen leverans, men du kan boka taxi eller kurir som hämtar beställningen. Vi lämnar över varorna till föraren och kan skicka en betalningslänk i förväg när ordern bekräftats.",
        }
        return f"<p>{paragraphs[ln]}</p><p>{follow[ln]}</p>"

    if _contains(qn, ["y-tunnus", "ytunnus", "y tunnus", "y-tunn", "business id", "company id", "företagsnummer", "y id"]):
        texts = {
            "fi": "Y-tunnuksemme on 3184994-7.",
            "en": "Our business ID is 3184994-7.",
            "sv": "Vårt FO-nummer är 3184994-7.",
        }
        return texts[ln]

    if _contains(qn, ["lemmik", "eläin", "pet", "hund", "dog", "cat", "kissa", "koira", "kissa"]):
        large_terms = {"iso", "suuri", "suuret", "suuren", "big", "large", "stor", "stora"}
        if any(t in qn for t in large_terms):
            texts = {
                "fi": "Suuret koirat eivät valitettavasti sovi pieneen myymäläämme. Voimme pakata tilauksen valmiiksi odottamaan ulkopuolelle.",
                "en": "Large dogs aren’t a good fit inside our small shop. We’re happy to hand the order over outside.",
                "sv": "Stora hundar passar tyvärr inte i vår lilla butik. Vi lämnar gärna beställningen utanför.",
            }
            return texts[ln]
        texts = {
            "fi": "Pienet lemmikit ovat tervetulleita mukana käynnille, kunhan ne pysyvät sylissä tai hihnassa ja muiden asiakkaiden huomioiminen onnistuu.",
            "en": "Small pets are welcome to visit as long as they’re carried or on a leash and comfortable around other customers.",
            "sv": "Små husdjur är välkomna så länge de bärs eller hålls i koppel och trivs bland andra kunder.",
        }
        return texts[ln]

    if _contains(qn, ["kuit", "receipt", "lasku", "invoice"]) and _contains(qn, ["yritys", "yrityk", "company", "företag"]):
        texts = {
            "fi": "Saat yrityksen nimellä paperikuitin noudon yhteydessä. Jos tarvitset laskun tai muuta lisätietoa, lähetä tilauksen tiedot sähköpostitse osoitteeseen rakaskotileipomo@gmail.com.",
            "en": "We can provide a paper receipt under your company name when you pick up. If you need an invoice or extra details, email the order information to rakaskotileipomo@gmail.com.",
            "sv": "Vi kan ge ett papperskvitto i företagets namn vid avhämtning. Behöver du faktura eller fler uppgifter, mejla beställningen till rakaskotileipomo@gmail.com.",
        }
        return texts[ln]

    if _contains(qn, ["pöyd", "table", "seat"]) and _contains(qn, ["varaa", "varata", "book", "reserve", "reservation", "reservera"]):
        texts = {
            "fi": "Emme tarjoa pöytävarauksia tai asiakaspaikkoja – myymälä toimii noutopisteenä.",
            "en": "We don’t have seating or table reservations—the shop is takeaway only.",
            "sv": "Vi har inga sittplatser eller bordsbokningar – butiken är en ren avhämtningspunkt.",
        }
        return texts[ln]

    if _contains(qn, ["wc", "toilet", "restroom"]):
        texts = {
            "fi": "Meillä ei valitettavasti ole asiakas-WC:tä.",
            "en": "We don’t have a customer restroom, sorry.",
            "sv": "Tyvärr har vi ingen kundtoalett.",
        }
        return texts[ln]

    if _contains(qn, [
        "asiakaspaikka", "asiakaspaikkoja", "istumapaikka", "istumapaikkoja", "istuma", "istua", "istumaan",
        "seating", "seat", "sit down", "mahtuu", "kapasiteet", "capacity"
    ]):
        texts = {
            "fi": "Myymälämme on noutopiste ilman istumapaikkoja – tuotteet pakataan mukaan.",
            "en": "We operate as a takeaway shop—there’s no indoor seating.",
            "sv": "Butiken är en take-away punkt – vi har inga sittplatser.",
        }
        return texts[ln]

    if _contains(qn, ["kesä", "talvi", "season"] ) and _contains(qn, ["aukiolo", "hours"]):
        texts = {
            "fi": "Perusaukiolomme ovat To–Pe 11–17 ja La 11–15. Mahdolliset kausimuutokset päivitämme verkkosivuille ja Googleen.",
            "en": "Our standard hours are Thu–Fri 11–17 and Sat 11–15. Any seasonal changes are announced on our website and Google listing.",
            "sv": "Våra ordinarie tider är tors–fre 11–17 och lör 11–15. Eventuella säsongsändringar meddelas på webbplatsen och Google.",
        }
        return texts[ln]

    if _contains(qn, ["tuore", "eniten", "fresh"] ) and _contains(qn, ["piirak", "piirakka"]) and _contains(qn, ["milloin", "mihin", "when"]):
        texts = {
            "fi": "Tuoreimmat piirakat ovat tarjolla heti, kun avaamme: torstaisin ja perjantaisin klo 11 sekä lauantaisin klo 11.",
            "en": "You’ll find the freshest pies right at opening—Thu & Fri 11:00 and Sat 11:00.",
            "sv": "De färskaste pirogerna finns direkt vid öppning – tors & fre kl. 11 samt lör kl. 11.",
        }
        return texts[ln]

    if (_contains(qn, ["tuore", "uunituore"])) and _contains(qn, ["pakaste", "raakapakaste", "frozen", "djupfryst", "fryst"]):
        paragraphs = {
            "fi": "Piirakoitamme saa sekä uunituoreina myymälästä että raakapakasteina (10 tai 20 kpl pakkaukset) kotiin paistettavaksi.",
            "en": "We sell our pies both fresh from the shop and as par-baked frozen packs (10 or 20 pies) that you can finish at home.",
            "sv": "Vi säljer våra piroger både nygräddade i butiken och som råfrysta förpackningar (10 eller 20 st) att grädda hemma.",
        }
        return f"<p>{paragraphs[ln]}</p>{_suggest_menu_block(ln)}"

    if _contains(qn, ["pelkk", "pelkästään"] ) and _contains(qn, ["ruis", "rye"]) and _contains(qn, ["taikin", "degen"]):
        texts = {
            "fi": "Karjalanpiirakan kuori on sataprosenttista ruista – emme lisää vehnää taikinaan.",
            "en": "Our Karelian pie crusts are 100% rye with no wheat added.",
            "sv": "Skalet i våra karelska piroger består till 100 % av råg, utan vetetillsats.",
        }
        return texts[ln]

    if _contains(qn, ["perunahiut", "potato flakes"]):
        texts = {
            "fi": "Käytämme lisäaineettomia perunahiutaleita ja keitettyä perunaa – teemme täytteen itse leipomolla.",
            "en": "We combine additive-free potato flakes with cooked potato—so the mash is prepared in-house.",
            "sv": "Vi använder tillsatsfria potatisflingor tillsammans med kokt potatis – fyllningen görs i bageriet.",
        }
        return texts[ln]

    if _contains(qn, ["ohje", "ohjet", "ohjeet", "paisto-ohje", "paisto-ohjeet"]) and _contains(qn, ["piirakka", "piirak", "pirog"]):
        texts = {
            "fi": (
                "Kotona paista raakapakastepiirakat 250–275 °C uunissa noin 18–20 minuuttia ja anna vetäytyä hetki."
                " Jos lämmität valmiiksi paistettuja piirakoita, 200–220 °C ja 10–12 minuuttia riittää, kunnes pinta on rapea."
            ),
            "en": (
                "Bake raw-frozen pies at 250–275 °C for about 18–20 minutes, then let them rest briefly."
                " For reheating already baked pies, use 200–220 °C for roughly 10–12 minutes until crisp."
            ),
            "sv": (
                "Grädda råfrysta piroger i 250–275 °C i cirka 18–20 minuter och låt dem vila en stund."
                " För att värma färdiggräddade piroger räcker 200–220 °C i ungefär 10–12 minuter tills de är krispiga."
            ),
        }
        return texts[ln]

    if _contains(qn, ["lämm", "lämmit" ]) and _contains(qn, ["pakastepiir", "frozen pie"]):
        texts = {
            "fi": "Lämmitä pakastepiirakka 200–220 °C uunissa noin 10–12 minuuttia, kunnes pinta on rapea ja sisus kuuma.",
            "en": "Reheat a frozen pie in a 200–220 °C oven for about 10–12 minutes until hot and crisp.",
            "sv": "Värm en fryst pirog i 200–220 °C ugn i cirka 10–12 minuter tills den är varm och krispig.",
        }
        return texts[ln]

    if _contains(qn, ["paista", "bake"]) and _contains(qn, ["raakapakaste", "raw-frozen", "par-baked"]):
        texts = {
            "fi": "Paista raakapakastepiirakat 250–275 °C uunissa noin 18–20 minuuttia. Anna vetäytyä hetki ennen tarjoilua.",
            "en": "Bake raw-frozen pies at 250–275 °C for about 18–20 minutes, then let them rest briefly before serving.",
            "sv": "Grädda råfrysta piroger i 250–275 °C i cirka 18–20 minuter och låt dem vila en stund före servering.",
        }
        return texts[ln]

    if _contains(qn, ["kuinka monta", "montako", "how many"]) and _contains(qn, ["puss", "pak", "bag"]) and _contains(qn, ["piirakka", "piirak", "pirog"]):
        texts = {
            "fi": "Raakapakastepussissa on joko 10 tai 20 piirakkaa – valitse tarvitsemasi koko.",
            "en": "Our frozen packs come with either 10 or 20 pies—pick the size that suits you.",
            "sv": "Våra råfrysta förpackningar innehåller antingen 10 eller 20 piroger – välj den storlek som passar dig.",
        }
        return texts[ln]

    if _contains(qn, ["irto", "yksittä", "loose"]) and _contains(qn, ["piirakka", "piirak", "pirog"]):
        texts = {
            "fi": "Kyllä, voit ostaa karjalanpiirakoita sekä yksittäin että 10/20 kappaleen pakkauksissa.",
            "en": "Yes, you can buy pies individually over the counter or in 10 / 20 piece packs.",
            "sv": "Ja, du kan köpa karelska piroger styckvis i butiken eller i paket om 10 / 20 stycken.",
        }
        return texts[ln]

    if _contains(qn, ["kuinka kauan", "kauanko", "how long"]) and _contains(qn, ["pakastim", "freezer"]) and _contains(qn, ["piirakka", "piirak", "pirog"]):
        texts = {
            "fi": "Kypsäpakasteet kannattaa käyttää noin kahden kuukauden kuluessa, raakapakasteet säilyvät jopa 6 kuukautta.",
            "en": "Ready-baked frozen pies are best within about 2 months; raw-frozen pies keep up to 6 months.",
            "sv": "Färdiggräddade fryspiroger håller cirka 2 månader; råfrysta piroger upp till 6 månader.",
        }
        return texts[ln]

    if _contains(qn, ["paistovalmi", "ready to bake", "par-baked"]) and _contains(qn, ["piirakka", "piirak", "pirog"]):
        texts = {
            "fi": "Kyllä – raakapakasteet ovat valmiiksi muotoiltuja, joten voit paistaa ne helposti kotiuunissa.",
            "en": "Yes, our raw-frozen pies are ready to bake and go straight into your home oven.",
            "sv": "Ja, våra råfrysta piroger är färdiga att gräddas direkt i hemmaugnen.",
        }
        return texts[ln]

    if _contains(qn, ["käsin", "handmade", "handgjord"]) and _contains(qn, ["piirakka", "piirak", "pirog"]):
        texts = {
            "fi": "Kyllä – jokainen piirakka rypytetään käsin Vallilan leipomollamme.",
            "en": "Yes—every pie is crimped by hand in our Vallila bakery.",
            "sv": "Ja – varje pirog nypas för hand i vårt bageri i Vallila.",
        }
        return texts[ln]
    if "samos" in qn and _contains(qn, ["aina", "jatku", "usein", "saatavilla", "available"]):
        texts = {
            "fi": "Samosat kuuluvat vakiovalikoimaamme ja niitä löytyy lähes aina vitriinistä. Suurempaan määrään suosittelemme ennakkotilausta, jotta varmasti riittää kaikille.",
            "en": "Samosas are part of our core range and are almost always available. For larger quantities we suggest preordering so we can set aside enough for you.",
            "sv": "Samosor ingår i vårt fasta sortiment och finns nästan alltid framme. För större mängder rekommenderar vi att du förboka så att vi kan lägga undan åt dig.",
        }
        return texts[ln]

    if "samos" in qn and _contains(qn, ["täytt", "täyte", "fylln", "fill"]):
        texts = {
            "fi": "Tarjolla on vegaaninen gobi-samosa (kukkakaali, peruna, herneet, mausteet) sekä kana-samosa. Molemmat ovat lempeän mausteisia intialaisia leivonnaisia.",
            "en": "We make a vegan gobi samosa with cauliflower, potato, peas and spices, plus a chicken samosa. Both are gently spiced Indian pastries.",
            "sv": "Vi erbjuder en vegansk gobi-samosa med blomkål, potatis, ärtor och kryddor samt en kycklingsamosa. Båda är smakrika med mild hetta.",
        }
        return texts[ln]

    if _contains(qn, ["suolaisia", "suolainen"]) and _contains(qn, ["muiden", "muun", "other"]) and _contains(qn, ["täytte", "filling"]):
        texts = {
            "fi": "Karjalanpiirakoidemme vakitäytteet ovat riisi, peruna, ohra ja vegaaninen riisi. Muita suolaisia täytemakuja emme tällä hetkellä tarjoa.",
            "en": "Our savoury Karelian pies come in four fillings: rice, potato, barley and a vegan rice option. We don’t offer additional savoury fillings right now.",
            "sv": "Våra salta karelska piroger finns med fyra fyllningar: ris, potatis, korn och en vegansk risvariant. Vi har för närvarande inga andra salta fyllningar.",
        }
        return texts[ln]

    if "gobi" in qn and _contains(qn, ["vegaan", "vegansk", "vegan"]):
        texts = {
            "fi": "Kyllä – gobi-samosa on täysin vegaaninen ja sisältää kukkakaalia, perunaa, herneitä ja mausteita.",
            "en": "Yes, the gobi samosa is fully vegan with cauliflower, potato, peas and spices.",
            "sv": "Ja, gobi-samosan är helt vegansk med blomkål, potatis, ärtor och kryddor.",
        }
        return texts[ln]

    if "samos" in qn and _contains(qn, ["mauste", "perinte", "traditional"]):
        texts = {
            "fi": "Käytämme perinteisiä intialaisia mausteita kuten jeeraa, korianteria, kurkumaa, garam masalaa ja chiliä.",
            "en": "We season them with traditional Indian spices such as cumin, coriander, turmeric, garam masala and chili.",
            "sv": "Vi kryddar samosorna med klassiska indiska kryddor som spiskummin, koriander, gurkmeja, garam masala och chili.",
        }
        return texts[ln]

    if "samos" in qn and _contains(qn, ["annos", "annoksessa", "portion", "pack"]):
        texts = {
            "fi": "Tuoreita samosoja voi ostaa yksittäin. Raakapakastepakkaus sisältää 5 samosaa.",
            "en": "Fresh samosas are sold individually, while our freezer pack contains 5 pieces.",
            "sv": "Färska samosor säljs styckvis, och våra råfrysta förpackningar innehåller 5 stycken.",
        }
        return texts[ln]

    if "samos" in qn and _contains(qn, ["iso", "koko", "size"]):
        texts = {
            "fi": "Samosat ovat kämmenen kokoisia, noin 100–120 g kappale.",
            "en": "Each samosa is palm-sized, roughly 100–120 g.",
            "sv": "Samosorna är handflatsstora och väger cirka 100–120 g per styck.",
        }
        return texts[ln]

    if "samos" in qn and _contains(qn, ["pakast", "freeze", "frysa"]):
        texts = {
            "fi": "Voit pakastaa samosat kotona – lämmitä ne 200 °C uunissa noin 20–25 minuuttia.",
            "en": "You can freeze leftover samosas at home and reheat at 200 °C for about 20–25 minutes.",
            "sv": "Du kan frysa samosorna hemma och värma dem i 200 °C ugn i cirka 20–25 minuter.",
        }
        return texts[ln]

    if "samos" in qn and _contains(qn, ["tulinen", "spicy", "hot"]):
        texts = {
            "fi": "Samosat ovat lempeän mausteisia – eivät kovin tulisia. Pyydä rohkeasti lisäpotkua, jos haluat.",
            "en": "They’re mildly spiced rather than hot; let us know if you’d like extra heat.",
            "sv": "Samosorna har mjuk hetta och är inte starka – säg till om du vill ha extra styrka.",
        }
        return texts[ln]

    if "samos" in qn and _contains(qn, ["dippi", "kastike", "dip"]):
        texts = {
            "fi": "Dippi ei sisälly vakiona, mutta suosittelemme esimerkiksi jogurtti-minttukastiketta tai mango chutneyta rinnalle.",
            "en": "We don’t include a dip by default, but recommend pairing them with yogurt-mint sauce or mango chutney.",
            "sv": "Dippsås ingår inte som standard, men vi rekommenderar yoghurt-myntasås eller mango chutney vid sidan.",
        }
        return texts[ln]

    if "samos" in qn and _contains(qn, ["maa", "resept", "recipe"]):
        texts = {
            "fi": "Resepti tulee Rakan kotiseudulta Intiasta – vegaaninen gobi on perheresepti ja kana-samosa maustetaan samalla tyylillä.",
            "en": "The recipe comes from Raka’s home region in India—the vegan gobi is a family recipe and the chicken samosa follows the same spice profile.",
            "sv": "Receptet kommer från Rakas hemtrakter i Indien – den veganska gobin är ett familjerecept och kycklingsamosan kryddas i samma stil.",
        }
        return texts[ln]

    if "samos" in qn and _contains(qn, ["vehn", "vete", "wheat"]):
        texts = {
            "fi": "Samosoiden taikinassa käytämme vehnäjauhoja, joten tuote ei ole gluteeniton.",
            "en": "The samosa dough contains wheat flour, so they’re not gluten-free.",
            "sv": "Degenn till samosorna innehåller vetemjöl och är därför inte glutenfri.",
        }
        return texts[ln]

    if _contains(qn, ["soija", "soijaa", "soy"]):
        texts = {
            "fi": "Emme käytä soijaa tuotteissamme.",
            "en": "We do not use soy in our products.",
            "sv": "Vi använder inte soja i våra produkter.",
        }
        return texts[ln]

    if _contains(qn, ["mobilepay"]):
        texts = {
            "fi": "MobilePay ei valitettavasti käy maksutapana. Suosittelemme korttimaksua.",
            "en": "We don’t support MobilePay at the moment; please use a card.",
            "sv": "MobilePay fungerar tyvärr inte som betalningsmetod. Använd kort i stället.",
        }
        return texts[ln]

    if _contains(qn, ["lasku", "invoice"]):
        texts = {
            "fi": "Yrityslaskutus onnistuu tapauskohtaisesti – ota yhteyttä osoitteeseen rakaskotileipomo@gmail.com ja kerro tilauksesi.",
            "en": "We handle invoicing case by case; email us at rakaskotileipomo@gmail.com with your order details.",
            "sv": "Fakturering ordnar vi från fall till fall – mejla oss på rakaskotileipomo@gmail.com med dina orderuppgifter.",
        }
        return texts[ln]

    if _contains(qn, ["wolt", "foodora"]):
        texts = {
            "fi": "Emme ole Woltissa tai Foodorassa – tilaukset noudetaan suoraan leipomolta tai voit lähettää kuljettajan hakemaan tilauksen.",
            "en": "We’re not on Wolt or Foodora; please pick up directly from the bakery or arrange your own courier.",
            "sv": "Vi finns inte på Wolt eller Foodora – hämta i bageriet eller ordna egen kurir.",
        }
        return texts[ln]

    if _contains(qn, ["koulu", "päiväkod", "school", "daycare"]):
        texts = {
            "fi": "Meillä ei juuri nyt ole aktiivista yhteistyötä koulujen tai päiväkotien kanssa, mutta kuulemme mielellämme ideoista – laita viesti osoitteeseen rakaskotileipomo@gmail.com.",
            "en": "We’re not currently running a school or daycare program, but we’re happy to discuss ideas—drop us a line at rakaskotileipomo@gmail.com.",
            "sv": "Vi har ingen aktivt samarbete med skolor eller daghem för tillfället, men dela gärna dina idéer via rakaskotileipomo@gmail.com.",
        }
        return texts[ln]

    if _contains(qn, ["sunnunt", "söndag", "sunday"]):
        texts = {
            "fi": "Olemme aina kiinni sunnuntaisin – pidämme silloin lepopäivän.",
            "en": "We’re closed every Sunday – that’s our day off.",
            "sv": "Vi håller alltid stängt på söndagar – då har vi vilodag.",
        }
        return texts[ln]

    if _contains(qn, ["juhlapyh", "holiday", "poikkeus", "exception hours"]):
        texts = {
            "fi": "Ilmoitamme poikkeavat aukioloajat verkkosivuillamme ja Google-profiilissa. Kurkkaa sieltä ennen kuin lähdet.",
            "en": "Any holiday hours are posted on our website and Google listing—please check there before visiting.",
            "sv": "Eventuella helgöppettider publiceras på vår webbplats och Google-profil – kika där innan du kommer.",
        }
        return texts[ln]

    if _contains(qn, ["mihin aikaan", "milloin kannattaa", "juuri paistettu", "fresh" ]) and _contains(qn, ["piirakka", "piirak", "come", "tulla", "saapua", "komma"]):
        texts = {
            "fi": "Tuoreimmat piirakat löytyvät heti avauksen aikaan: to–pe klo 11 ja la klo 11. Ennakkotilauksen voi noutaa sovittuna aikana.",
            "en": "You’ll find the freshest pies right at opening—Thu–Fri 11:00 and Sat 11:00. Preorders are ready at your agreed pickup time.",
            "sv": "De färskaste pirogerna finns vid öppning: tors–fre kl. 11 och lör kl. 11. Förbeställningar ligger klara den avtalade tiden.",
        }
        return texts[ln]

    if ln == "fi" and ("maks" in qn and "kort" in qn):
        return "Maksut vain kortilla, ja lähes kaikki kortit käyvät."

    if _contains(qn, ["custom cake", "tilauskakku", "tilaus kakku", "beställningstårta", "beställningst\u00e5rta", "beställningst\u00e5r", "tårta", "kakku"]) and _contains(qn, ["custom", "tilaus", "beställ"]):
        texts = {
            "fi": "Emme leivo kakkuja (täytekakkuja, kuivakakkuja), voileipäkakkuja, lihapiirakoita tai konditoriatuotteita. Olemme ensisijaisesti karjalanpiirakkaleipomo.",
            "en": "We don’t bake cakes (layer cakes, loaf cakes), sandwich cakes, meat pies, or confectionery items. We are primarily a Karelian pie bakery.",
            "sv": "Vi bakar inte tårtor (gräddtårtor eller mjuka kakor), smörgåstårtor, köttpiroger eller konditorivaror. Vi är i första hand ett karelskt pirogbageri.",
        }
        return texts[ln]

    if _contains(qn, ["pakaste", "pakast", "frozen", "djupfryst", "frysta"]):
        return _frozen_response(ln)

    if _contains(qn, ["säily", "kuinka kauan", "how long", "hur länge", "keep at home", "säilyvät", "säilyy", "kest" ]) and _contains(qn, ["piir", "pie", "piro"]):
        texts = {
            "fi": "Piirakkamme säilyvät jääkaapissa noin 2–3 päivää. Kaikki paistetut tuotteemme voi myös pakastaa, jolloin ne säilyvät noin kaksi kuukautta.",
            "en": "Our pies keep in the fridge for about 2–3 days. All of our baked products can also be frozen, and they keep for roughly two months in the freezer.",
            "sv": "Våra piroger håller i kylskåp i cirka 2–3 dagar. Alla bakverk går även att frysa in och håller då ungefär två månader i frysen.",
        }
        return texts[ln]

    if _contains(qn, ["osoit", "address", "adress", "where are you", "var ligger", "missä sijaitsette", "missä olette", "var finns"]):
        texts = {
            "fi": "Myymälämme sijaitsee Vallilassa osoitteessa Kumpulantie 15, 00520 Helsinki.",
            "en": "Our bakery is in Vallila at Kumpulantie 15, 00520 Helsinki.",
            "sv": "Vår butik finns i Vallila på Kumpulantie 15, 00520 Helsingfors.",
        }
        return texts[ln]

    if _contains(qn, ["catering", "pitopalvel", "pitopalvelu", "juhlatilaus"]):
        texts = {
            "fi": "Otamme mielellämme isompiakin tilauksia juhliin ja tapahtumiin. Lähetä toiveesi ja aikataulusi sähköpostilla osoitteeseen rakaskotileipomo@gmail.com, niin suunnittelemme sopivan kokonaisuuden.",
            "en": "We’re happy to prepare larger orders for parties and events. Email your wishlist and timing to rakaskotileipomo@gmail.com and we’ll plan the right selection.",
            "sv": "Vi bakar gärna större mängder till fester och evenemang. Mejla dina önskemål och tidtabell till rakaskotileipomo@gmail.com så planerar vi en passande helhet.",
        }
        return texts[ln]

    if _contains(qn, ["samos"]) and _contains(qn, ["mauste", "maust", "spicy", "hot", "tul", "krydd"]):
        texts = {
            "fi": "Samosamme maustetaan kymmenillä intialaisilla mausteilla kuten juustokuminalla, korianterilla, kurkumalla, garam masalalla ja miedolla chilillä. Ne ovat aromikkaita ja lempeän tulisia.",
            "en": "Our samosas are seasoned with a dozen Indian spices – cumin, coriander, turmeric, garam masala and a mild chili, among others. They’re flavorful with a gentle heat.",
            "sv": "Våra samosor kryddas med ett tiotal indiska kryddor som spiskummin, koriander, gurkmeja, garam masala och mild chili. De är smakrika med mjuk hetta.",
        }
        return texts[ln]

    if _contains(qn, ["kardemumm", "cardamom"]):
        texts = {
            "fi": "Käytämme pullissa kokonaisia kardemumman siemeniä, jotka jauhamme itse tuoreiksi juuri ennen taikinan valmistusta. Kardemumma tuodaan perheemme kautta Intiasta, joten aromi on erityisen raikas.",
            "en": "For our buns we use whole cardamom seeds that we grind ourselves right before mixing the dough. The cardamom is sourced from family growers in India, so the flavor stays intensely fresh.",
            "sv": "Till bullarna använder vi hela kardemummafrön som vi mal själva precis innan degen blandas. Kardemumman kommer från vår familj i Indien, vilket ger en extra frisk och aromatisk smak.",
        }
        return texts[ln]

    if _contains(qn, ["allerg", "allerge"]):
        texts = {
            "fi": "Yleisimmät allergeenit joita käytämme: maito, gluteeni (vehnä/ruis/ohra) ja kananmuna. Käsittelemme leipomossa viljaa ja maitotuotteita; ristikontaminaatiota ei voida täysin poissulkea. Verkkokaupassa jokaisella tuotteella on allergiatiedot, ja voit myös kysyä minulta yksittäisen tuotteen allergeeneista.",
            "en": "The main allergens we handle are milk, gluten (wheat/rye/barley) and egg. We work with flour and dairy in the bakery, so cross-contamination cannot be fully excluded. Each product in the online shop lists its allergens, and you can ask me about a specific item here as well.",
            "sv": "De vanligaste allergenerna vi använder är mjölk, gluten (vete/råg/korn) och ägg. Vi hanterar mjöl och mejeriprodukter i bageriet, så korskontaminering kan inte helt uteslutas. I webbutiken finns allergener för varje produkt och du kan fråga mig om enskilda produkter här.",
        }
        return texts[ln]

    if _contains(qn, ["toimit", "kuljet", "delivery", "deliver", "hemleverans", "hemleverera", "kotiin", "home delivery"]):
        texts = {
            "fi": "Kyllä, tilaukset voi noutaa myymälästämme aukioloaikoina – suuremmat erät onnistuvat myös tiistaisin ja keskiviikkoisin sopimalla etukäteen. Emme tarjoa kotiinkuljetusta, mutta voit tilata taksin tai muun kuljetuspalvelun noutamaan tilauksen. Luovutamme tuotteet kuljettajalle ja lähetämme tarvittaessa maksulinkin etukäteen, kun tilaus on vahvistettu.",
            "en": "Yes, you can pick up orders from our shop during opening hours – larger batches can also be collected on Tuesdays and Wednesdays by arrangement. We don’t offer home delivery, but you can book a taxi or courier to collect your order. We hand everything to the driver and can send a payment link in advance once the order is confirmed.",
            "sv": "Ja, du kan hämta beställningar i vår butik under öppettiderna – större satser kan även hämtas tisdagar och onsdagar enligt överenskommelse. Vi erbjuder ingen hemleverans, men du kan boka en taxi eller annan transport som hämtar beställningen. Vi lämnar över varorna till föraren och kan skicka en betalningslänk i förväg när beställningen är bekräftad.",
        }
        return texts[ln]

    if _contains(qn, ["kananmuna", "kananmun", "munaa", "munia", "egg"]):
        texts = {
            "fi": "Karjalanpiirakat ovat ilman kananmunaa, mutta pullat voitelemme ohuella kananmunapesulla ennen paistoa. Ennakkotilauksessa voimme jättää munavoitelun pois, jos toivot.",
            "en": "Our Karelian pies are egg-free, but we brush the buns with a light egg wash before baking. In a preorder we can skip the egg wash if you prefer.",
            "sv": "Våra karelska piroger är utan ägg, men bullarna penslas lätt med ägg före gräddning. Vid förbeställning kan vi hoppa över äggpenslingen om du vill.",
        }
        return texts[ln]

    if _contains(qn, ["samos"]) and _contains(qn, ["maito", "maitotuotte", "dairy", "mjölk", "mjolk"]):
        texts = {
            "fi": "Vegaaninen gobi-samosa ei sisällä maitotuotteita. Kana-samosassa käytämme laktoositonta jogurttia marinadissa, joten siinä on maitoproteiinia.",
            "en": "The vegan gobi samosa contains no dairy. Our chicken samosa uses lactose-free yogurt in the marinade, so it does contain milk protein.",
            "sv": "Den veganska gobi-samosan innehåller inga mejeriprodukter. Kycklingsamosan innehåller laktosfri yoghurt i marinaden och har därför mjölkprotein.",
        }
        return texts[ln]

    if _contains(qn, ["sähköpost", "email"]) and _contains(qn, ["tilaa", "tilauk", "order"]):
        texts = {
            "fi": "Voit tehdä tilauksen myös sähköpostilla – lähetä viesti osoitteeseen rakaskotileipomo@gmail.com ja kerro tuotteet, määrät ja noutoaika.",
            "en": "Yes, you can order by email: send the products, quantities and desired pickup time to rakaskotileipomo@gmail.com.",
            "sv": "Ja, du kan beställa via e-post – skriv produkter, mängder och önskad avhämtning till rakaskotileipomo@gmail.com.",
        }
        return texts[ln]

    if _contains(qn, ["kuitt", "receipt"]) and _contains(qn, ["sähköpost", "email"]):
        texts = {
            "fi": "Verkkokauppa lähettää kuitin sähköpostiisi automaattisesti. Myymälästä saat paperikuitin ja pyynnöstä myös PDF:n.",
            "en": "The online shop emails a receipt automatically. In-store we provide a paper receipt and can email a PDF if needed.",
            "sv": "Webbutiken mejlar kvittot automatiskt. I butiken får du ett papperskvitto och vi kan mejla en PDF vid behov.",
        }
        return texts[ln]

    if _contains(qn, ["lahjakort", "gift card", "presentkort", "voucher"]):
        texts = {
            "fi": "Valitettavasti emme myy lahjakortteja.",
            "en": "Unfortunately we do not sell gift cards.",
            "sv": "Tyvärr säljer vi inte presentkort.",
        }
        return texts[ln]

    if _contains(qn, ["täsm", "mihin aikaan", "milloin", "what time", "vilken tid", "kellon", "time", "voinko siirt", "kuinka myöh", "how late", "latest pickup", "latest time"]) and \
       _contains(qn, ["torst", "thursday", "torsdag"]) and \
       _contains(qn, ["nout", "pick up", "pickup", "hämt", "hamta", "hämta", "noutoon", "noutaa"]):
        texts = {
            "fi": "Torstaisin palvelemme klo 11–17. Nouda tilauksesi tuona aikavälinä leipomolta.",
            "en": "On Thursdays we’re open from 11:00 to 17:00—please pick up your order within that window.",
            "sv": "På torsdagar har vi öppet kl. 11–17. Hämta din beställning inom det tidsintervallet.",
        }
        return texts[ln]

    if _contains(qn, ["täsm", "mihin aikaan", "milloin", "what time", "vilken tid", "kellon", "time", "voinko siirt", "kuinka myöh", "how late", "latest pickup", "latest time"]) and \
       _contains(qn, ["perjant", "friday", "fredag"]) and \
       _contains(qn, ["nout", "pick up", "pickup", "hämt", "hamta", "hämta", "noutoon", "noutaa"]):
        texts = {
            "fi": "Perjantaisin olemme avoinna klo 11–17, joten noudot tulee tehdä tuon aikavälin puitteissa.",
            "en": "On Fridays we’re open 11:00–17:00, so please plan your pickup within those hours.",
            "sv": "På fredagar har vi öppet kl. 11–17 – hämta beställningen under den tiden.",
        }
        return texts[ln]

    if _contains(qn, ["täsm", "mihin aikaan", "milloin", "what time", "vilken tid", "kellon", "time", "voinko siirt", "kuinka myöh", "how late", "latest pickup", "latest time"]) and \
       _contains(qn, ["lauant", "saturday", "lördag", "lordag"]) and \
       _contains(qn, ["nout", "pick up", "pickup", "hämt", "hamta", "hämta", "noutoon", "noutaa"]):
        texts = {
            "fi": "Lauantaisin palvelemme klo 11–15, joten noudot tulee tehdä viimeistään klo 15 mennessä.",
            "en": "On Saturdays we’re open 11:00–15:00, so make sure to pick up before 15:00.",
            "sv": "På lördagar har vi öppet kl. 11–15, så hämta din beställning före kl. 15.",
        }
        return texts[ln]

    if _contains(qn, ["siirt", "myöh", "parilla tunnilla", "pari tunt", "couple hours", "couple of hours", "later", "delay", "shift", "move", "push", "resched"]) and _contains(qn, ["nout", "pick up", "pickup", "hämt", "hamta", "hämta"]):
        texts = {
            "fi": "Voit siirtää noudon samalle päivälle, kunhan ehdit ennen sulkemista: to–pe klo 11–17 ja la klo 11–15. Jos aikataulu muuttuu paljon, laitathan meille viestin osoitteeseen rakaskotileipomo@gmail.com.",
            "en": "You can shift the pickup later the same day as long as you arrive before closing: Thu–Fri 11:00–17:00 and Sat 11:00–15:00. If the timing changes more, please email us at rakaskotileipomo@gmail.com.",
            "sv": "Du kan flytta upphämtningen samma dag så länge du kommer före stängning: tors–fre kl. 11–17 och lör kl. 11–15. Om tiden ändras mer, mejla oss gärna på rakaskotileipomo@gmail.com.",
        }
        return texts[ln]

    if _contains(qn, ["käte", "cash", "kontant", "kontanter", "käteis", "käteisellä"]) or \
       (_contains(qn, ["maksu", "maksaa", "pay", "payment"]) and _contains(qn, ["käte", "cash", "kontant"])):
        texts = {
            "fi": "Hyväksymme yleisimmät pankki- ja luottokortit lähimaksulla. Emme hyväksy MobilePayta, käteistä tai shekkejä.",
            "en": "We accept major debit and credit cards with contactless. We do not accept MobilePay, cash or checks.",
            "sv": "Vi accepterar ledande debit- och kreditkort med kontaktlös betalning. Vi accepterar inte MobilePay, kontanter eller checkar.",
        }
        return texts[ln]

    if _contains(qn, ["muutta", "muokata", "peru", "perua", "cancel", "change", "avboka", "ändra"]) and _contains(qn, ["tilaus", "tilauk", "order", "beställning", "bestallning", "bestall", "order"]):
        texts = {
            "fi": (
                "Jos haluat muuttaa tai perua tilauksen, lähetä sähköpostia osoitteeseen rakaskotileipomo@gmail.com mahdollisimman pian."
                " Kun leivonta on alkanut, emme aina pysty tekemään muutoksia."
            ),
            "en": (
                "To modify or cancel an order, please email rakaskotileipomo@gmail.com as soon as possible."
                " Once we begin baking, changes may no longer be possible."
            ),
            "sv": (
                "Behöver du ändra eller avboka en beställning? Mejla oss snarast på rakaskotileipomo@gmail.com."
                " När bakningen väl har startat kan ändringar vara svåra."
            ),
        }
        return texts[ln]

    if _contains(qn, ["kuinka iso", "suurin", "largest", "how big"]) and _contains(qn, ["tilaus", "order"]):
        texts = {
            "fi": "Voimme paistaa useita satoja piirakoita kerralla – kerro määrä ja noutoaika sähköpostilla, niin vahvistamme aikataulun.",
            "en": "We can bake several hundred pies in one batch. Email your quantity and pickup time and we’ll confirm the schedule.",
            "sv": "Vi kan grädda flera hundra piroger åt gången. Mejla mängd och avhämtningstid så bekräftar vi planeringen.",
        }
        return texts[ln]

    if _contains(qn, ["tapahtum", "event"]) and _contains(qn, ["yhteisty", "collab", "partner"]):
        texts = {
            "fi": "Teemme mielellämme yhteistyötä tapahtumien kanssa – lähetä tapahtuman tiedot osoitteeseen rakaskotileipomo@gmail.com.",
            "en": "We’re open to event collaborations—email the details to rakaskotileipomo@gmail.com.",
            "sv": "Vi samarbetar gärna med evenemang – skicka detaljerna till rakaskotileipomo@gmail.com.",
        }
        return texts[ln]

    if _contains(qn, ["minimitilaus", "minimum order", "minsta beställning"]) and _contains(qn, ["koti", "delivery", "kuljetus"]):
        texts = {
            "fi": "Emme tarjoa kotiinkuljetusta, joten minimitilaus koskee vain noutoja myymälästä.",
            "en": "We don’t have home delivery, so there’s no delivery minimum—orders are always picked up in store.",
            "sv": "Vi erbjuder ingen hemleverans, så det finns ingen minimiorder för leverans – allt hämtas i butiken.",
        }
        return texts[ln]

    if _contains(qn, ["muutama", "pari", "only a few", "small order"]):
        texts = {
            "fi": "Voit hyvin ostaa vain muutaman tuotteen – mitään minimitilausta ei ole noudettaessa.",
            "en": "Yes, feel free to order just a few pieces—there’s no minimum when you pick up.",
            "sv": "Ja, du kan beställa bara några få produkter – det finns ingen minimiorder vid avhämtning.",
        }
        return texts[ln]

    if _contains(qn, ["raakapakaste", "raw-frozen", "par-baked"]) and _contains(qn, ["tilaa", "order", "ostaa"]):
        texts = {
            "fi": "Raakapakasteet löydät verkkokaupastamme – valitse pakkauskoko (10 tai 20 kpl) ja nouda aukioloaikoina.",
            "en": "You can order the raw-frozen items in our online shop—choose a 10 or 20 piece pack and pick up during opening hours.",
            "sv": "Beställ råfrysta produkter i webbutiken – välj 10- eller 20-pack och hämta under öppettiderna.",
        }
        return texts[ln]

    return None


def _is_product_inquiry(query: str, lang: str) -> bool:
    qn = normalize(query)
    toks = set(tokens(query))
    # Negative guards: gift card queries should NOT be treated as product overview
    neg = {"lahjakortti", "lahjakortteja", "gift card", "gift cards", "presentkort"}
    if any(k in qn for k in neg) or (toks & neg):
        return False

    # If the question is about dietary filters or seasonal/special items, defer to specific answers
    exclusions = {
        "vegaan", "vegansk", "vegan",
        "maidot", "mjölkfri", "dairy", "milk-free", "milk free",
        "laktoos", "laktos",
        "gluteen", "gluten",
        "kausi", "seson", "season",
        "erikoistarj", "special offer", "specials",
        "valmisseos", "premix", "mix", "alusta asti", "from scratch", "ennakkomaks", "lahjoit", "hävikk", "haavik",
    }
    if any(term in qn for term in exclusions):
        return False

    if lang == "fi":
        menu_terms = {
            # menu/selection/product nouns
            "menu", "ruokalista", "valikoima", "valikoimassa",
            "tuote", "tuotte", "tuotteet", "tuotteita", "tuotteit", "tuotteiden",
            "leivonnainen", "leivonnaiset", "leivonnaisia",
            # concrete product names
            "karjalanpiirakka", "piirakka", "samosa", "curry", "twist", "pull", "mustikkakukko",
        }
        verb_hints = {"myytte", "myyttekö", "myydä", "myykö", "leipoa", "leivo", "leivot", "leivotte", "leivomme"}
        # Require either a menu/product noun, or a verb plus a generic noun
        if (toks & menu_terms) or any(k in qn for k in menu_terms):
            return True
        if (toks & verb_hints) and ("tuote" in qn or "tuotte" in qn or "leivonnai" in qn or "leivo" in qn):
            return True
        # Special phrasing
        if "mitä te leivotte" in qn or "mitä tuotteita" in qn:
            return True
        return False
    if lang == "sv":
        menu_terms = {"meny", "sortiment", "produkt", "produkter", "bakverk", "pirog", "piroger", "samosa", "curry", "twist", "bulle", "mustikkakukko"}
        if (toks & menu_terms) or any(k in qn for k in menu_terms):
            return True
        return False
    # en
    menu_terms = {"menu", "selection", "product", "products", "pastry", "pastries", "pie", "pies", "karelian", "samosa", "curry", "twist", "bun", "blueberry pie", "mustikkakukko"}
    if (toks & menu_terms) or any(k in qn for k in menu_terms):
        return True
    return False


def _compose_products_overview(lang: str) -> str:
    if lang == "sv":
        body = (
            "Vår huvudprodukt är karelska piroger med 100 % rågskal. "
            "På den salta sidan har vi indiska bakverk som samosor och mungcurry-twists. "
            "Bland de söta alternativen finns finska bullar och blåbärspaj (mustikkakukko). "
            "Vi bakar inte tårtor, smörgåstårtor eller andra konditorivaror."
        )
        return f"{body}\n{_suggest_menu_block(lang)}"
    if lang == "en":
        body = (
            "Our signature product is the Karelian pie with a 100% rye crust. "
            "Savory options include Indian pastries like samosas and mung curry twists. "
            "For sweets we bake Finnish buns and blueberry pie (mustikkakukko). "
            "We don’t bake cakes, sandwich cakes or other confectionery."
        )
        return f"{body}\n{_suggest_menu_block(lang)}"
    # fi default
    body = (
        "Päätuotteemme on 100 % rukiisella kuorella leivottu karjalanpiirakka. "
        "Suolaiselta puolelta löytyy myös intialaisia leivonnaisia kuten samosat ja mungcurry-twistit. "
        "Makeista tarjoamme suomalaisia pullia ja mustikkakukkoa. "
        "Emme leivo täyte- tai voileipäkakkuja emmekä muita konditoriatuotteita."
    )
    return f"{body}\n{_suggest_menu_block(lang)}"


def _extract_answer_text(doc: Doc, query_norm: str | None = None) -> Tuple[str, str]:
    text = doc.text or ""
    if "\n" in text:
        q_part, a_part = text.split("\n", 1)
    else:
        q_part, a_part = text, ""
    q_part = q_part.strip()
    if q_part.lower().startswith("q:"):
        q_clean = q_part[2:].strip()
    else:
        q_clean = q_part
    a_clean = a_part
    if a_clean.lower().startswith("a:"):
        a_clean = a_clean[2:].strip()
    else:
        a_clean = a_clean.strip()
    return q_clean, a_clean


def compose_answer(query: str, hits: List[Tuple[float, Doc]], lang: str) -> str:
    special = _special_answer(query, lang)
    if special:
        return special

    if not hits:
        if lang == "fi":
            return "En ole varma. Voitko täsmentää kysymystä?"
        if lang == "sv":
            return "Jag är inte säker. Kan du precisera frågan?"
        return "I’m not sure. Could you clarify your question?"

    # Prefer an exact FAQ match if present
    qn = normalize(query)
    for _, d in hits:
        dq, da = _extract_answer_text(d)
        if normalize(dq) == qn:
            if da:
                return da

    # Enforce preferred ordering for product/menu inquiries
    if _is_product_inquiry(query, lang):
        return _compose_products_overview(lang)

    # Default: use the first good FAQ-like snippet
    top = hits[:3]
    for _, d in top:
        _, txt = _extract_answer_text(d)
        if txt:
            return txt
    # Fallback to any snippet/meta
    d0 = top[0][1]
    return d0.meta.get("snippet") or d0.meta.get("summary") or d0.meta.get("source") or d0.id
