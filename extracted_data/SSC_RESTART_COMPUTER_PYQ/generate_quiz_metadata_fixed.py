#!/usr/bin/env python3
"""
Generate quiz-bank metadata from question-bank JSON files.

Subtopics are inferred from each question's wording and explanation using
topic-aware, ordered rules. The source question JSON is never modified.
Questions that do not match a specific rule are placed in a meaningful
topic-specific fallback bucket rather than the generic "Uncategorized".
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


def clean_name(value: Any, field: str, question_number: int) -> str:
    if value is None:
        return "Uncategorized"
    value = str(value).strip()
    return value or "Uncategorized"


def make_bank_key(source: Path) -> str:
    # Ignore browser/download duplicate suffixes such as "(2)" so that
    # SSC_RESTART_COMPUTER_PYQ(2).json keeps the canonical bank key.
    stem = re.sub(r"\s*\(\d+\)$", "", source.stem).strip()
    name = re.sub(r"[^A-Za-z0-9]+", "_", stem)
    return re.sub(r"_+", "_", name).strip("_").lower() or "quiz_bank"


# Ordered topic-specific rules. First matching rule wins.
RULES: dict[str, list[tuple[str, str]]] = {
    "Computer Fundamentals & New Tech": [
        (r"\b(characteristic|diligence|versatility|accuracy|gigo|speed of a computer|no iq|power of remembrance)\b", "Characteristics of Computers"),
        (r"\b(generation[s]? of computers?|first generation|second generation|third generation|fourth generation|fifth generation|vacuum tube|microprocessor|transistor)\b", "Computer Generations & History"),
        (r"\b(charles babbage|alan turing|ada lovelace|john von neumann|pascaline|analytical engine|difference engine|eniac|edvac|univac|mark i|stored.program)\b", "Computer Pioneers & Early Computers"),
        (r"\b(ascii|ebcdic|unicode|character encoding|binary coded decimal|bcd code)\b", "Character Encoding & Codes"),
        (r"\b(application[s]? of computers?|computer[s]? used in|computer[s]? in (?:education|banking|business|entertainment|research|medicine|industry)|reservation system|e-commerce|scientific research|weather forecasting)\b", "Applications of Computers"),
        (r"\b(cad|cam|rfid|3d print|cgi|animation|multimedia|file format|\.wma|\.mp3|\.wav)\b", "Computer Applications & Digital Technologies"),
        (r"\b(supercomputer|mainframe|workstation|microcomputer|laptop|notebook|tablet computer|types of computers?)\b", "Types of Computers"),
        (r"\b(input.process.output|ipo cycle|computer system|data processing|computer works)\b", "Computer System & IPO Cycle"),
    ],
    "CPU, Hardware & I/O Devices": [
        (r"\b(central processing unit|\bcpu\b|control unit|\bcu\b|arithmetic logic unit|\balu\b|instruction cycle|fetch|decode|execute|register|program counter|instruction register|memory address register|accumulator|pipelining|clock speed|ipc\b|multi.core|processor|von neumann|harvard architecture|microprogrammed|hardwired control)\b", "CPU Architecture & Processing"),
        (r"\b(input device|keyboard|mouse|scanner|ocr|barcode|touchscreen|trackball|joystick|microphone|webcam|light pen|digitizer)\b", "Input Devices"),
        (r"\b(output device|monitor|display|visual display unit|\bvdu\b|printer|plotter|speaker|projector)\b", "Output Devices"),
        (r"\b(port\b|usb|hdmi|displayport|vga|serial port|parallel port|ps/2|connector|interface|rts/cts|handshaking)\b", "Ports & Interfaces"),
        (r"\b(motherboard|printed circuit board|\bpcb\b|chipset|bus\b|data bus|address bus|system bus|expansion slot|smps|power supply|cmos|bios|uefi|firmware|booting|cold boot|warm boot)\b", "Motherboard, BIOS & System Hardware"),
        (r"\b(device[s]?|hardware|computer components|system unit|embedded system|soc\b|system.on.chip)\b", "Computer Hardware & Components"),
    ],
    "Memory & Storage Devices": [
        (r"\b(cache memory|\bcache\b|sram|dram|ram\b|rom\b|volatile|non.volatile|primary memory|main memory|secondary memory|virtual memory|memory hierarchy|memory unit|memory chip|prom|eprom|eeprom)\b", "Computer Memory & Memory Types"),
        (r"\b(hard disk|hdd|solid.state|ssd|optical disc|cd.rom|dvd|blu.ray|pen drive|flash drive|usb drive|memory card|magnetic tape|external drive)\b", "Storage Devices & Media"),
        (r"\b(capacity|storage capacity|bit\b|byte\b|kilobyte|megabyte|gigabyte|terabyte|petabyte|data storage unit|access time|seek time|data transfer rate)\b", "Storage Units & Performance"),
        (r"\b(file|folder|directory|filesystem|file system|formatting|partition|disk cleanup|defragment)\b", "File & Disk Management"),
    ],
    "Software, OS & Programming": [
        (r"\b(compiler|interpreter|assembler|assembly language|machine language|high.level language|low.level language|programming language|syntax analysis|lexical analysis|semantic analysis|source code|object code|program translation)\b", "Programming Languages & Translators"),
        (r"\b(scheduling|fifo|fcfs|round.robin|convoy effect|process management|process scheduling|multitasking|deadlock|kernel|memory management|virtual file system|root directory|directory|file system|file metadata|unix command|linux command|shell|command.line)\b", "Operating System Concepts & File Systems"),
        (r"\b(operating system|\bos\b|windows|linux|unix|macos|android|ios|desktop operating|open.source operating)\b", "Operating Systems"),
        (r"\b(device driver|driver software|utility software|disk cleanup|disk defragment|system software|application software|general purpose software|customized software|firmware|system library|software classification|winzip|compression software)\b", "Types of Software & Device Drivers"),
        (r"\b(gui\b|graphical user interface|command.line interface|\bcli\b|user interface|text editor|text formatter|ole\b)\b", "User Interfaces & Software Tools"),
        (r"\b(sql|database)\b", "Database & Data Software"),
    ],
    "Microsoft Windows": [
        (r"\b(task manager|processes tab|performance tab|startup apps|startup tab|resource monitor|cpu utilization|gpu utilization|not responding|end task|priority of a process|services tab)\b", "Task Manager & System Monitoring"),
        (r"\b(file explorer|windows explorer|recycle bin|quick access|wildcard|file name|filename|folder|directory|rename|delete.*file|restore.*file|sort.*file|search.*file|move.*file|copy.*file|create.*folder|file management|file extension|\.exe\b|\.dll\b|\.sys\b|powershell|command prompt|cmd\b|dir /|remove-item)\b", "File Explorer & File Management"),
        (r"\b(shortcut key|keyboard shortcut|alt \+|ctrl \+|shift \+|windows key|start menu|tab key|hotkey)\b", "Keyboard Shortcuts & Navigation"),
        (r"\b(sleep|hibernate|hibernation|shutdown|restart|reboot|power mode|power saving|battery|screen timeout|power & sleep|cold boot|warm boot)\b", "Power, Sleep & Startup Options"),
        (r"\b(settings|control panel|personaliz|wallpaper|desktop background|screen resolution|theme|screensaver|display settings|sound settings|user account control|\buac\b|safe.?search|remote desktop)\b", "Windows Settings & Personalization"),
        (r"\b(taskbar|notification area|system tray|desktop icon|icon|window[s]?|maximize|minimi[sz]e|restore down|virtual desktop|snap|start button)\b", "Windows Desktop & Interface"),
        (r"\b(windows 7|windows 10|windows 11|version of windows|windows xp|windows operating system|windows os)\b", "Windows Versions & Features"),
        (r"\b(cloud|onedrive|synchroni[sz]|backup|restore point|file history|recovery)\b", "Backup, Sync & Recovery"),
    ],
    "MS Word": [
        (r"\b(mail merge|mailing|recipient list|merge field|envelope|label)\b", "Mail Merge"),
        (r"\b(table|rows and columns|cell|split cells|merge cells|convert text to table|table design|table layout)\b", "Tables"),
        (r"\b(header|footer|page number|page border|margin|orientation|page size|section break|page break|columns|print|printing|print preview)\b", "Page Layout & Printing"),
        (r"\b(footnote|endnote|citation|bibliography|table of contents|index|cross.reference|caption|reference tab)\b", "References & Document Indexing"),
        (r"\b(track changes|comment|review|accept changes|reject changes|proofread|spelling|grammar|thesaurus|word count|language|translate)\b", "Review, Proofing & Collaboration"),
        (r"\b(font|bold|italic|underline|font size|font color|text effect|character spacing|highlight|change case|format painter|text formatting)\b", "Font & Text Formatting"),
        (r"\b(paragraph|line spacing|indent|alignment|align left|align right|justify|bullets|numbering|tabs|borders and shading|paragraph spacing)\b", "Paragraph Formatting & Lists"),
        (r"\b(picture|image|shape|wordart|smartart|chart|text box|object|wrap text|illustration|graphic|clip art)\b", "Images, Shapes & Objects"),
        (r"\b(find|replace|navigation pane|select all|clipboard|cut|copy|paste|undo|redo|keyboard shortcut|shortcut key|ctrl\s*[+])\b", "Keyboard Shortcuts & Editing"),
        (r"\b(save|save as|open|close|new document|file extension|docx|\.doc\b|template|document properties|compatibility mode|protected view)\b", "Files, Saving & Document Management"),
        (r"\b(view|ruler|zoom|navigation pane|read mode|web layout|print layout|status bar|ribbon|quick access toolbar|interface|tab in word)\b", "Word Interface & Document Views"),
    ],
    "MS Excel": [
        (r"\b(sumif|sumifs|countif|countifs|averageif|averageifs|iferror|ifna|vlookup|hlookup|xlookup|index\(|match\(|lookup\(|choose\(|filter\(|sort\(|unique\(|subtotal\(|aggregate\(|networkdays|workday|dateif|textjoin|concat|concatenate|left\(|right\(|mid\(|len\(|proper\(|upper\(|lower\(|rept\(|replace\(|substitute\(|char\(|code\(|dec2|bin2|hex2|oct2|mod\(|sqrt\(|abs\(|round|int\(|max\(|min\(|counta?\(|average\(|median\(|rank|formula[s]?|function[s]?|nested function)\b", "Formulas & Functions"),
        (r"\b(cell reference|cell address|absolute reference|relative reference|mixed reference|dollar sign|\$[a-z]{1,3}\$?\d+|range\b|named range|name manager|row and column|worksheet cell)\b", "Cell References, Ranges & Names"),
        (r"\b(chart|graph|pie chart|bar chart|column chart|line chart|sparkline|data visualization)\b", "Charts & Data Visualization"),
        (r"\b(sort|filter|auto.?filter|advanced filter|data validation|remove duplicates|text to columns|flash fill|consolidat|subtotal|what.if|goal seek|scenario|solver|pivot table|pivotchart)\b", "Data Tools, Sorting & Filtering"),
        (r"\b(conditional formatting|format as table|cell style|number format|currency format|percentage format|date format|alignment|wrap text|merge cells|font|fill color|borders|formatting)\b", "Cell Formatting & Conditional Formatting"),
        (r"\b(worksheet|workbook|sheet tab|insert.*sheet|delete.*sheet|rename.*sheet|hide.*sheet|unhide.*sheet|group.*sheet|protect.*sheet|freeze panes|split window|navigation between sheets)\b", "Workbooks & Worksheets"),
        (r"\b(print|printing|print preview|page layout|page break|print area|margins|orientation|page setup|header|footer|fit to page)\b", "Page Layout & Printing"),
        (r"\b(shortcut|keyboard|ctrl\s*[+]|shift\s*[+]|alt\s*[+]|function key|f2\b|f4\b|quick access toolbar)\b", "Keyboard Shortcuts & Editing"),
        (r"\b(csv|file format|save as|open|save|xlsx|xls\b|xlsm|export|import|compatibility mode|template|protected view)\b", "Files, Formats & Import/Export"),
        (r"\b(data type|text to number|number stored as text|error value|#div/0|#value|#ref|#name|#n/a|#num|#null|####|formula error|calculation|recalculate)\b", "Data Types, Calculation & Errors"),
        (r"\b(macro|vba|visual basic|developer tab|record macro)\b", "Macros & Automation"),
        (r"\b(view|zoom|status bar|formula bar|name box|ribbon|interface|gridlines|page break preview|normal view)\b", "Excel Interface & Views"),
    ],
    "MS PowerPoint": [
        (r"\b(slide show|presenter view|rehearse|record.*slide|transition|animation|timing)\b", "Slide Shows, Transitions & Animations"),
        (r"\b(design ideas|theme|template|slide layout|background|slide master|master slide|design tab)\b", "Slide Design, Themes & Masters"),
        (r"\b(slide sorter|normal view|reading view|outline view|notes page|view tab|reorder.*slide|organis.*slide)\b", "Slide Views & Organization"),
        (r"\b(text box|shape|picture|image|audio|video|chart|table|smartart|wordart|object|media|insert tab)\b", "Text, Images & Multimedia"),
        (r"\b(shortcut|keyboard|ctrl\s*[+]|shift\s*[+]|alt\s*[+]|function key|save|print|open|close|protected view|file format|pptx|ppt\b)\b", "Shortcuts & Presentation Management"),
    ],
    "Computer Networks": [
        (r"\b(protocol|tcp|udp|ip address|ipv4|ipv6|http|https|ftp|smtp|pop3|imap|dns|dhcp|arp|icmp|osi|tcp/ip|port number)\b", "Network Protocols & Addressing"),
        (r"\b(topology|bus topology|star topology|ring topology|mesh topology|network topology)\b", "Network Topologies"),
        (r"\b(lan\b|wan\b|man\b|pan\b|wlan|intranet|extranet|internet network|network type|local area|wide area|metropolitan area)\b", "Network Types & Coverage"),
        (r"\b(router|switch|hub|gateway|repeater|bridge|modem|nic\b|network interface card|access point|network device)\b", "Networking Devices & Components"),
        (r"\b(mac address|physical address|network adapter|ethernet|wifi|wi.fi|wireless|bandwidth|transmission|data communication|packet|client.server|peer.to.peer)\b", "Data Communication & Network Technologies"),
    ],
    "Internet, E-mail & E-Banking": [
        (r"\b(e.mail|email|gmail|outlook|bcc|cc in an e.mail|smtp|imap|pop3|mail user agent|mail submission|mail transfer|inbox|outbox|spam|attachment|email client|email address|email header|email signature|forward.*message|reply.*email|draft folder|contacts list)\b", "E-mail & Messaging"),
        (r"\b(browser|google chrome|firefox|edge browser|address bar|browser tab|incognito|private browsing|download|upload|url\b|uniform resource locator|hyperlink|web page|website|world wide web|\bwww\b|web server|domain name|dns|http|https|static website|dynamic website|html)\b", "Web Browsers, WWW & Websites"),
        (r"\b(search engine|search query|bing|google search|search result|search filter|exact phrase|web search|search operator)\b", "Search Engines & Web Search"),
        (r"\b(e.bank|banking|upi|atm|neft|rtgs|imps|mobile banking|net banking|internet banking|debit card|credit card|online payment|digital payment|payment gateway|ifsc|secure transaction)\b", "E-Banking & Digital Payments"),
        (r"\b(e.commerce|ecommerce|online shopping|marketplace|flipkart|amazon|online transaction|business.to.consumer|b2b|b2c)\b", "E-commerce & Online Services"),
        (r"\b(video conferencing|voip|chat|instant messaging|social media|blog|rss|teleconferencing|communication technology)\b", "Online Communication & Collaboration"),
        (r"\b(internet service provider|\bisp\b|broadband|wifi|wi.fi|hotspot|internet connection|network access|intranet|extranet)\b", "Internet Connectivity & Services"),
    ],
    "Cyber Security & Malware": [
        (r"\b(virus|worm|trojan|ransomware|spyware|adware|rootkit|keylogger|boot sector|malware|antivirus|anti.virus)\b", "Malware & Antivirus"),
        (r"\b(phishing|spear phishing|social engineering|spoofing|identity theft|shoulder surfing|spam|fraud|scam)\b", "Phishing, Scams & Social Engineering"),
        (r"\b(ddos|dos attack|denial.of.service|firewall|intrusion|botnet|hacking|cyberattack|cyber attack|brute.force|sql injection)\b", "Cyberattacks & Network Security"),
        (r"\b(encrypt|decrypt|cryptography|hashing|hash function|digital signature|certificate|public key|private key|ssl|tls|https|integrity|authentication|authorization)\b", "Encryption, Authentication & Data Integrity"),
        (r"\b(password|passphrase|multi.factor|two.factor|2fa|access control|permission|privacy|secure browsing|backup|security practice)\b", "Passwords, Privacy & Safe Computing"),
    ],
    "Number System, Codes & Logic Gates": [
        (r"\b(logic gate|nand|nor|xor|xnor|and gate|or gate|not gate|truth table|boolean)\b", "Logic Gates & Boolean Algebra"),
        (r"\b(ascii|ebcdic|unicode|character code|code for character|bits per character)\b", "Character Codes"),
        (r"\b(binary|decimal|octal|hexadecimal|base of|number system|convert|equivalent of decimal|binary equivalent)\b", "Number Systems & Conversions"),
    ],
    "Database Management System (DBMS)": [
        (r"\b(sql|structured query language|select|insert|update|delete|create|alter|drop|ddl|dml|dcl|tcl|query language)\b", "SQL & Database Commands"),
        (r"\b(primary key|foreign key|candidate key|composite key|super key|unique key|key constraint|referential integrity)\b", "Keys & Constraints"),
        (r"\b(row|record|tuple|column|field|attribute|table|relation|database schema|entity|relationship)\b", "Database Tables, Records & Fields"),
        (r"\b(dbms|database management|rdbms|relational database|normalization|normalisation|transaction|acid)\b", "DBMS Concepts & Relational Databases"),
    ],
    "Emerging Tech: AI, Cloud, IoT & Blockchain": [
        (r"\b(artificial intelligence|\bai\b|machine learning|deep learning|chatgpt|generative ai|large language model|llm|neural network|natural language processing)\b", "Artificial Intelligence & Machine Learning"),
        (r"\b(cloud|saas|paas|iaas|software as a service|platform as a service|infrastructure as a service|virtual machine)\b", "Cloud Computing & Service Models"),
        (r"\b(internet of things|\biot\b|smart device|sensor|connected device)\b", "Internet of Things (IoT)"),
        (r"\b(blockchain|distributed ledger|bitcoin|cryptocurrency|smart contract)\b", "Blockchain & Distributed Ledger"),
    ],
    "Multimedia & Digital Literacy": [
        (r"\b(multimedia|audio|video|animation|text.*image|media element)\b", "Multimedia Concepts"),
        (r"\b(raster|bitmap|vector|jpeg|jpg|png|gif|bmp|svg|image format|image file)\b", "Digital Images & File Formats"),
        (r"\b(upi|digital payment|digital india|digilocker|digital document|e.governance|digital literacy|online citizen service)\b", "Digital India & Digital Services"),
    ],
}


FALLBACKS = {
    "Computer Fundamentals & New Tech": "General Computer Fundamentals",
    "CPU, Hardware & I/O Devices": "Other Hardware & I/O Concepts",
    "Memory & Storage Devices": "Other Memory & Storage Concepts",
    "Software, OS & Programming": "Other Software & OS Concepts",
    "Microsoft Windows": "Other Windows Features",
    "MS Word": "Other MS Word Features",
    "MS Excel": "Other MS Excel Features",
    "MS PowerPoint": "Other PowerPoint Features",
    "Computer Networks": "Other Networking Concepts",
    "Internet, E-mail & E-Banking": "Other Internet & Online Services",
    "Cyber Security & Malware": "Other Cyber Security Concepts",
    "Number System, Codes & Logic Gates": "Other Number System & Logic Concepts",
    "Database Management System (DBMS)": "Other DBMS Concepts",
    "Emerging Tech: AI, Cloud, IoT & Blockchain": "Other Emerging Technologies",
    "Multimedia & Digital Literacy": "Other Multimedia & Digital Literacy",
}


def infer_subtopic(question: dict[str, Any]) -> str:
    # Respect an explicitly supplied conceptual subtopic if it is meaningful.
    explicit = question.get("subtopic")
    if isinstance(explicit, str) and explicit.strip() and explicit.strip().lower() not in {
        "uncategorized", "other", "misc", "general"
    }:
        return explicit.strip()

    topic = clean_name(question.get("topic"), "topic", 0)
    text = " ".join(str(question.get(k) or "") for k in ("q", "exp", "o"))
    text = re.sub(r"\s+", " ", text).lower()
    for pattern, label in RULES.get(topic, []):
        if re.search(pattern, text, flags=re.IGNORECASE):
            return label
    return FALLBACKS.get(topic, "Other Concepts")


def build_metadata(questions: list[dict[str, Any]], bank_key: str) -> dict[str, Any]:
    topic_groups: OrderedDict[str, OrderedDict[str, int]] = OrderedDict()
    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            raise ValueError(f"Question at array position {index} is not a JSON object.")
        topic = clean_name(question.get("topic"), "topic", index)
        subtopic = infer_subtopic(question)
        topic_groups.setdefault(topic, OrderedDict())
        topic_groups[topic][subtopic] = topic_groups[topic].get(subtopic, 0) + 1

    topics = []
    for topic_name, subtopic_counts in topic_groups.items():
        subtopics = [{"name": name, "count": count} for name, count in subtopic_counts.items()]
        topics.append({
            "name": topic_name,
            "count": sum(subtopic_counts.values()),
            "subtopics": subtopics,
        })

    metadata = {
        "schemaVersion": 1,
        "bankKey": bank_key,
        "totalCount": len(questions),
        "topicCount": len(topics),
        "topics": topics,
    }
    topic_total = sum(t["count"] for t in topics)
    subtopic_total = sum(s["count"] for t in topics for s in t["subtopics"])
    if topic_total != len(questions) or subtopic_total != len(questions):
        raise RuntimeError("Metadata count validation failed.")
    return metadata


def load_questions(source: Path) -> list[dict[str, Any]]:
    try:
        with source.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {source}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if isinstance(data, list):
        questions = data
    elif isinstance(data, dict):
        questions = next((data[k] for k in ("questions", "data", "items")
                          if isinstance(data.get(k), list)), None)
        if questions is None:
            raise ValueError(f"{source} has no question array under questions/data/items.")
    else:
        raise ValueError(f"{source} must contain a JSON array or wrapped question array.")
    if not questions:
        raise ValueError(f"No questions found in {source}.")
    return questions


def process_file(source: Path, bank_key: str | None = None,
                 output_dir: Path | None = None) -> Path:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Input JSON file not found: {source}")
    questions = load_questions(source)
    metadata = build_metadata(questions, bank_key or make_bank_key(source))
    destination_dir = output_dir.resolve() if output_dir else source.parent
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{source.stem}_METADATA.json"
    with destination.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return destination


def find_json_files(paths: list[str], recursive: bool) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_file():
            if path.suffix.lower() == ".json" and not path.stem.endswith("_METADATA"):
                found.append(path)
        elif path.is_dir():
            iterator = path.rglob("*.json") if recursive else path.glob("*.json")
            found.extend(p for p in iterator if p.is_file() and not p.stem.endswith("_METADATA"))
        else:
            print(f"WARNING: Skipping missing path: {path}", file=sys.stderr)
    unique, seen = [], set()
    for item in found:
        identity = str(item.resolve()).lower()
        if identity not in seen:
            seen.add(identity)
            unique.append(item)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate metadata with inferred conceptual subtopics from quiz question banks."
    )
    parser.add_argument("inputs", nargs="+", help="Question JSON files or folders.")
    parser.add_argument("--recursive", action="store_true", help="Search folders recursively.")
    parser.add_argument("--bank-key", help="Override bankKey (one input file only).")
    parser.add_argument("--output-dir", type=Path, help="Write metadata to this folder.")
    args = parser.parse_args()
    sources = find_json_files(args.inputs, args.recursive)
    if not sources:
        print("ERROR: No question-bank JSON files found.", file=sys.stderr)
        return 1
    if args.bank_key and len(sources) != 1:
        print("ERROR: --bank-key can only be used with one input JSON file.", file=sys.stderr)
        return 1
    failures = 0
    for source in sources:
        try:
            destination = process_file(source, args.bank_key, args.output_dir)
            metadata = json.loads(destination.read_text(encoding="utf-8"))
            subtopic_count = sum(len(t["subtopics"]) for t in metadata["topics"])
            print(
                f"OK  {source.name} -> {destination}\n"
                f"    Questions: {metadata['totalCount']:,} | Topics: {metadata['topicCount']} | "
                f"Subtopics: {subtopic_count}"
            )
            for topic in metadata["topics"]:
                print(f"    {topic['name']}: " + ", ".join(
                    f"{s['name']} ({s['count']})" for s in topic["subtopics"]
                ))
        except Exception as exc:
            failures += 1
            print(f"ERROR processing {source}: {exc}", file=sys.stderr)
    print(f"\nFinished: {len(sources) - failures} succeeded, {failures} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
