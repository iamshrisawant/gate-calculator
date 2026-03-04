import pdfplumber
import json
import re

def extract_marks_from_paper(source):
    """
    Extracts mappings of Question Number -> Marks (1.0 or 2.0) from the Question Paper text.
    Returns: dict mapping str(q_no) -> float(marks)
    """
    marks_map = {}
    if not source:
        return marks_map

    # Need to seek back to 0 if it's a stream
    if hasattr(source, 'seek'):
        source.seek(0)
        
    try:
        with pdfplumber.open(source) as pdf:
            text = "".join(page.extract_text() or "" for page in pdf.pages)
            # Find Q.X - Q.Y Carry ONE/TWO mark
            matches = re.finditer(r"Q\.(\d+)[^\d]+Q\.(\d+)\s+Carry\s+(ONE|TWO)\s+mark", text, re.IGNORECASE)
            for m in matches:
                start = int(m.group(1))
                end = int(m.group(2))
                mark_val = 1.0 if m.group(3).upper() == "ONE" else 2.0
                for q in range(start, end + 1):
                    marks_map[str(q)] = mark_val
    except Exception as e:
        print(f"Error extracting marks from question paper: {e}")

    # If stream, seek back to 0 for later use if any
    if hasattr(source, 'seek'):
        source.seek(0)
    
    return marks_map

def extract_answer_key(source, output_path=None, paper_code=None, paper_source=None):
    """
    source: filepath (str) or file-like object (BytesIO)
    """
    schema = {}
    
    marks_map = {}
    if paper_source:
        print("Extracting marks from question paper...")
        marks_map = extract_marks_from_paper(paper_source)
        
    # pdfplumber.open supports both path and file-like objects
    with pdfplumber.open(source) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                # Skip header row if it contains "Q.No." or "Question No"
                start_idx = 0
                if table[0][0] and ("No" in table[0][0] or "Session" in table[0][0]):
                    start_idx = 1
                
                for row in table[start_idx:]:
                    if not row or len(row) < 4:
                        continue
                    
                    if len(row) >= 6:
                        # Old Row format: [Q.No, Session, Que.Type, Sec. Name, Key, Marks]
                        q_no = row[0]
                        q_type = row[2]
                        section = row[3]
                        key = row[4]
                        marks = row[5]
                    else:
                        # New 2026 Row format: ['Q. No.', 'Q. Type', 'Section', 'Key/Range']
                        q_no = row[0]
                        q_type = row[1]
                        section = row[2]
                        key = row[3]
                        # Fetch mark from question paper extract
                        marks = marks_map.get(str(q_no), 1.0) # default to 1.0 if not found

                    # Standardize Section Name for Regex Matching (GA, CS, DA, etc.)
                    raw_section = section.strip()
                    clean_section = raw_section
                    
                    # 1. General Aptitude -> GA
                    if "general aptitude" in raw_section.lower():
                        clean_section = "GA"
                    # 2. If we have a paper_code (e.g. CS) and section is NOT GA, assume it's the subject
                    # This handles "Computer Science..." -> "CS"
                    elif paper_code and raw_section.lower() != "ga":
                        # If the raw section is the full name or matches code
                        clean_section = paper_code

                    schema_key = f"{clean_section}_{q_no}"
                    
                    schema[schema_key] = {
                        "question_no": int(q_no),
                        "section": clean_section,
                        "original_section": raw_section,
                        "question_type": q_type,
                        "key": key,
                        "marks": float(marks)
                    }

    print(f"Extracted {len(schema)} keys.")
    if output_path and isinstance(output_path, str):
        # Only write to file if output_path is provided and is string (local mode usually)
        # For cloud/bytes, we expect the caller to handle specific saving if needed
        # But for backward compatibility with local mode, we try to save if it looks like a path
        try:
             with open(output_path, "w") as f:
                json.dump(schema, f, indent=4)
             print(f"Saved schema to {output_path}")
        except:
             pass 
    
    return schema

def detect_metadata(source, filename=""):
    """
    source: filepath (str) or file-like object
    filename: original filename (str) for fallback detection
    """
    meta = {
        "year": "", 
        "paper_code": ""
    }
    
    # 1. Try Content First (Most Reliable)
    try:
        with pdfplumber.open(source) as pdf:
            # Check first page text
            text = pdf.pages[0].extract_text()
            if text:
                # Year: "GATE 2025" or just "2024" if GATE missing
                y_match = re.search(r"GATE\s?(\d{4})", text, re.IGNORECASE)
                if y_match:
                    meta["year"] = y_match.group(1)
                else:
                    # Fallback: look for 202x in first page
                    y_weak = re.search(r"\b(202\d)\b", text)
                    if y_weak:
                        meta["year"] = y_weak.group(1)

                # Paper Code Extraction logic
                code_match = re.search(r"Answer Key for .* \(([A-Z]{2}\d?)\)", text)
                if not code_match:
                     code_match = re.search(r"(?:Paper )?Code\s?:\s?([A-Z]{2}\d?)", text, re.IGNORECASE)
                if not code_match:
                     code_match = re.search(r"Subject\s?:\s?.* \(([A-Z]{2}\d?)\)", text, re.IGNORECASE)
                if not code_match:
                     codes = "AE|AG|AR|BM|BT|CE|CH|CS|CY|DA|EC|EE|ES|EY|GE|GG|IN|MA|ME|MN|MT|NM|PE|PH|PI|ST|TF|XE|XH|XL"
                     code_match = re.search(rf"\((({codes})\d?)\)", text)

                if code_match:
                    meta["paper_code"] = code_match.group(1).upper()
                    
                # Special Handling for Multi-Session Papers (CS, ME, CE, etc.)
                if meta["paper_code"] and not meta["paper_code"][-1].isdigit():
                    session_match = re.search(r"(?:Session|Shift)\s?(\d)", text, re.IGNORECASE)
                    if session_match:
                        meta["paper_code"] += session_match.group(1)
            
    except Exception as e:
        print(f"Error reading PDF content: {e}")

    # 2. Fallback to Filename if missing
    if filename:
        if not meta["year"]:
            y_short = re.search(r"([A-Z]{2})(\d{2})", filename) 
            if y_short:
                 meta["year"] = "20" + y_short.group(2)
            else:
                 y_full = re.search(r"GATE[-_]?\s?(20\d{2})", filename, re.IGNORECASE)
                 if y_full:
                     meta["year"] = y_full.group(1)
        
        if not meta["paper_code"]:
            codes = "AE|AG|AR|BM|BT|CE|CH|CS|CY|DA|EC|EE|ES|EY|GE|GG|IN|MA|ME|MN|MT|NM|PE|PH|PI|ST|TF|XE|XH|XL"
            c_match = re.search(rf"({codes})([1-9])(?!\d)", filename, re.IGNORECASE)
            if c_match:
                 meta["paper_code"] = c_match.group(1).upper() + c_match.group(2)
            else:
                c_match = re.search(rf"({codes})", filename, re.IGNORECASE)
                if c_match:
                    meta["paper_code"] = c_match.group(1).upper()
            
    return meta
