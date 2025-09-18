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
    if _contains(qn, ["karjalanpiir", "karelian", "karelsk"]) and _contains(qn, ["täyte", "täytt", "filling", "fyllning", "fyllningar"]):
        texts = {
            "fi": "Karjalanpiirakoissamme on neljä vakituista täytettä: riisipuuro, perunasose, ohrapuuro ja vegaaninen riisipuuro (ilman maitotuotteita).",
            "en": "We bake our Karelian pies with four fillings: rice porridge, mashed potato, barley porridge and a vegan rice porridge made without dairy.",
            "sv": "Våra karelska piroger finns med fyra fyllningar: risgrynsgröt, potatismos, korngröt och en vegansk risgröt utan mejeriprodukter.",
        }
        return texts[ln]

    if _contains(qn, ["laktoos", "lactose", "laktos"]):
        texts = {
            "fi": "Kaikki tuotteemme ovat laktoosittomia.",
            "en": "All our products are lactose-free.",
            "sv": "Alla våra produkter är laktosfria.",
        }
        return texts[ln]

    if _contains(qn, ["gluteen", "gluten"]):
        texts = {
            "fi": "Meillä ei ole valitettavasti gluteenittomia tuotteita. Tilamme eivät sovellu gluteenittomaan leivontaan muun leivonnan ohella jauhopölyn vuoksi.",
            "en": "Unfortunately we do not offer gluten-free products. Our bakery handles plenty of wheat and rye flour so we can’t guarantee a gluten-free environment.",
            "sv": "Tyvärr erbjuder vi inga glutenfria produkter. Bageriet hanterar vetemjöl och rågmjöl, så miljön är inte glutenfri.",
        }
        return texts[ln]

    if _contains(qn, ["etukäteen", "ennakk", "preorder", "pre-order", "pre order", "förbeställ", "förbeställning"]):
        return _order_ui_block(ln)

    if _contains(qn, ["verkkokaup", "nettisivu", "online shop", "online store", "webbutik", "webbshop", "shop online"]):
        notes = {
            "fi": "Tee tilaus verkkokaupassa, niin voimme vahvistaa sen heti—nouda myymälästä aukioloaikoina (emme tee toimituksia).",
            "en": "Place your order in the online shop and we’ll confirm it right away—pickup in store during opening hours (we don’t deliver).",
            "sv": "Lägg din beställning i webbutiken så bekräftar vi den direkt—hämta i butiken under öppettiderna (vi erbjuder ingen leverans).",
        }
        return _order_with_note(notes[ln], ln)

    if _contains(qn, ["yritys", "yritykselle", "b2b", "suuremp", "isompi erä", "tukku"]) and not _contains(qn, ["lasku", "invoice"]):
        notes = {
            "fi": "Yritysasiakkaat voivat tehdä suurempia tilauksia sähköpostitse rakaskotileipomo@gmail.com. Varaathan 2–3 päivää aikaa tuotantoa varten ja muistathan, että nouto tapahtuu myymälästämme.",
            "en": "Business customers can place larger orders by emailing rakaskotileipomo@gmail.com. Please allow 2–3 days for production; pickups are always from our shop.",
            "sv": "Företagskunder kan lägga större beställningar via e-post till rakaskotileipomo@gmail.com. Räkna med 2–3 dagar för bakningen och hämta beställningen i butiken.",
        }
        return _order_with_note(notes[ln], ln)

    if (
        _contains(qn, ["tilaus", "tilauk", "tilata", "order", "beställ", "bestalla", "beställa", "tilaa"])
        and not _contains(qn, ["minimum", "minimi", "minsta", "minimitilaus", "minimumorder"])
        and not _contains(qn, ["kakku", "cake"])
        and not _contains(qn, ["kuitt", "receipt", "muut", "few", "raaka", "ilman", "drop in", "walk in", "wolt", "foodora"])
    ):
        notes = {
            "fi": "Tilaukset kannattaa tehdä vähintään päivää ennen noutoa (suuremmat määrät 2–3 päivää etukäteen). Tilaukset ovat noudettavia; emme tee kuljetuksia.",
            "en": "Please place orders at least one day in advance; for larger batches allow 2–3 days. Orders are pickup-only; we don’t offer delivery.",
            "sv": "Lägg beställningar minst en dag i förväg; för större mängder behöver vi 2–3 dagar. Beställningarna hämtas i butiken – vi erbjuder ingen leverans.",
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

    if _contains(qn, ["julkis", "tram", "metro", "bus", "bussi", "spårvagn"]):
        texts = {
            "fi": "Perille pääset helposti julkisilla: raitiovaunut 7 ja 9 sekä bussit 55 ja 71 pysähtyvät Paavalin kirkon kohdalla, parin minuutin kävelymatkan päässä.",
            "en": "Trams 7 and 9 plus buses 55 and 71 stop near Paavalin kirkko, only a couple of minutes’ walk from us.",
            "sv": "Spårvagn 7 och 9 samt bussar 55 och 71 stannar vid Paavalin kyrka, någon minuts promenad från oss.",
        }
        return texts[ln]

    if _contains(qn, ["esteet", "accessible", "tillgänglig"]):
        texts = {
            "fi": "Sisäänkäynti on katutasossa ja ovella on matala kynnys. Autamme mielellämme tarvittaessa sisään.",
            "en": "The entrance is street level with a low threshold—we’re happy to help you in if needed.",
            "sv": "Ingången är i gatuplan med en låg tröskel – vi hjälper gärna till om du behöver assistans.",
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

    if _contains(qn, ["wc", "toilet", "restroom"]):
        texts = {
            "fi": "Meillä ei valitettavasti ole asiakas-WC:tä.",
            "en": "We don’t have a customer restroom, sorry.",
            "sv": "Tyvärr har vi ingen kundtoalett.",
        }
        return texts[ln]

    if _contains(qn, ["asiakaspaikka", "istumapaikka", "seating", "sit down"]):
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

    if _contains(qn, ["käteis", "cash"]):
        texts = {
            "fi": "Emme valitettavasti ota vastaan käteismaksuja – maksut hoituvat kortilla (lähimaksu käy).",
            "en": "We don’t accept cash; please pay by card (contactless works).",
            "sv": "Vi tar tyvärr inte emot kontanter – vänligen betala med kort (kontaktlöst fungerar).",
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

    if _contains(qn, ["catering", "pitopalvel", "suur", "isompi", "tilaisu", "juhliin"]):
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
            "fi": "Emme tarjoa kotiinkuljetusta, mutta voit tilata taksin tai kuljetuspalvelun noutamaan tilauksesi. Luovutamme tuotteet kuskille ja voimme lähettää maksulinkin etukäteen, kun tilaus on vahvistettu.",
            "en": "We don’t provide home delivery ourselves, but you’re welcome to book a taxi or courier to pick up your order. We’ll hand the products to the driver and can send a payment link in advance once the order is confirmed.",
            "sv": "Vi erbjuder ingen egen hemleverans, men du kan boka en taxi eller budtjänst som hämtar din beställning. Vi lämnar över produkterna till föraren och kan skicka en betalningslänk i förväg när beställningen är bekräftad.",
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

    if _contains(qn, ["muutta", "muokata", "change"]) and _contains(qn, ["tilauk", "order"]):
        texts = {
            "fi": "Ilmoita muutoksista mahdollisimman pian sähköpostitse – kun leivonta on alkanut emme aina voi tehdä muutoksia.",
            "en": "Please email us as soon as possible if you need to change an order; once we start baking, adjustments may not be possible.",
            "sv": "Meddela oss via e-post så snart som möjligt om du behöver ändra en beställning – när bakningen väl har börjat är ändringar svåra.",
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
        main = "Vår huvudprodukt är karelsk pirog bakad på fullkornsråg."
        savory = "Dessutom erbjuder vi salta indiska bakverk såsom samosor och currytwists."
        sweet = "På den söta sidan har vi finska bullar och blåbärspajer (mustikkakukko)."
        vegan = "Vi har också veganska alternativ; förbeställ gärna i webbutiken."
        return f"{main} {savory} {sweet} {vegan}"
    if lang == "en":
        main = "Our main product is a 100% whole‑rye Karelian pie."
        savory = "We also offer savory Indian pastries such as samosas and curry twists."
        sweet = "On the sweet side we have Finnish buns and blueberry pies (mustikkakukko)."
        vegan = "We also offer vegan options; we recommend preordering in the online shop."
        return f"{main} {savory} {sweet} {vegan}"
    # fi default
    main = "Päätuotteemme on täysrukiinen karjalanpiirakka."
    savory = "Lisäksi tarjoamme suolaisia intialaisia leivonnaisia, kuten samosat ja curry‑twistit."
    sweet = "Makealta puolelta löytyy suomalaisia pullia ja mustikkakukkoa."
    vegan = "Tarjoamme myös vegaanisia vaihtoehtoja; vegaanituotteet kannattaa tilata etukäteen verkkokaupasta."
    return f"{main} {savory} {sweet} {vegan}"


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

    # Enforce preferred ordering for product/menu inquiries
    if _is_product_inquiry(query, lang):
        return _compose_products_overview(lang)

    # Default: use the first good FAQ-like snippet
    def _extract_answer(t: str) -> str:
        if not t:
            return ""
        a = t.split("\nA:", 1)
        if len(a) == 2:
            return a[1].strip()
        return t.strip()

    top = hits[:3]
    for _, d in top:
        txt = _extract_answer(d.text)
        if txt:
            return txt
    # Fallback to any snippet/meta
    d0 = top[0][1]
    return d0.meta.get("snippet") or d0.meta.get("summary") or d0.meta.get("source") or d0.id
