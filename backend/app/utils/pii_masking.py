import re
from typing import Any, Dict, List, Union


# Regex patterns for Indian financial PII
PAN_PATTERN = re.compile(r"\b([A-Z]{5})([0-9]{4})([A-Z])\b", re.IGNORECASE)
AADHAAR_PATTERN = re.compile(r"\b([0-9]{4})[\s\-]?([0-9]{4})[\s\-]?([0-9]{4})\b")
PHONE_PATTERN = re.compile(r"(?:\+91[\s\-]?)?(?:0)?([6-9][0-9])([0-9]{6})([0-9]{2})\b")
BANK_ACCOUNT_PATTERN = re.compile(r"\b[0-9]{9,18}\b")


def mask_pan(pan: str) -> str:
    """
    Masks Indian PAN (10 chars): 'ABCDE1234F' -> 'XXXXX1234F'.
    Preserves last 5 characters (4 digits + 1 letter) for verification.
    """
    if not pan:
        return ""
    cleaned = pan.strip().upper()
    if len(cleaned) == 10 and re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", cleaned):
        return f"XXXXX{cleaned[5:]}"
    return pan


def mask_aadhaar(aadhaar: str) -> str:
    """
    Masks Indian Aadhaar (12 digits): '123456789012' -> 'XXXXXXXX9012'.
    Standard UIDAI compliant masking: masks first 8 digits, shows last 4.
    """
    if not aadhaar:
        return ""
    digits = re.sub(r"[\s\-]", "", aadhaar.strip())
    if len(digits) == 12 and digits.isdigit():
        return f"XXXXXXXX{digits[-4:]}"
    return aadhaar


def mask_phone(phone: str) -> str:
    """
    Masks Indian 10-digit mobile number: '9876543210' -> '98XXXXXX10'.
    Preserves leading 2 and trailing 2 digits.
    """
    if not phone:
        return ""
    cleaned = phone.strip()
    match = re.search(r"(?:\+91[\s\-]?)?(?:0)?([6-9][0-9])([0-9]{6})([0-9]{2})$", cleaned)
    if match:
        prefix = "+91 " if "+91" in cleaned else ""
        return f"{prefix}{match.group(1)}XXXXXX{match.group(3)}"
    return phone


def mask_bank_account(account_no: str) -> str:
    """
    Masks Bank Account Number (9-18 digits): masks all but last 4 digits.
    """
    if not account_no:
        return ""
    digits = re.sub(r"[\s\-]", "", str(account_no).strip())
    if 9 <= len(digits) <= 18 and digits.isdigit():
        return f"{'X' * (len(digits) - 4)}{digits[-4:]}"
    return str(account_no)


def mask_pii_text(text: str) -> str:
    """
    Scans a free-text string and masks all detected PANs, Aadhaars, and phone numbers.
    Used before logging transcripts or sending context to external LLMs.
    """
    if not text:
        return ""

    # Mask PANs: ABCDE1234F -> XXXXX1234F
    result = PAN_PATTERN.sub(r"XXXXX\2\3", text)

    # Mask Aadhaars: 1234 5678 9012 or 123456789012 -> XXXXXXXX9012
    result = AADHAAR_PATTERN.sub(r"XXXXXXXX\3", result)

    # Mask Mobile Phones: 9876543210 -> 98XXXXXX10
    result = PHONE_PATTERN.sub(r"\1XXXXXX\3", result)

    return result


def mask_pii(text: str) -> str:
    """
    Regex/NER pass -- phone numbers, PAN/Aadhaar patterns, bank accounts --
    run once at the very end of report assembly before PDF render.
    """
    return mask_pii_text(text)



def mask_pii_dict(data: Union[Dict[str, Any], List[Any], Any]) -> Union[Dict[str, Any], List[Any], Any]:
    """
    Recursively masks sensitive PII values in nested dictionaries or lists.
    """
    if isinstance(data, dict):
        masked_dict = {}
        for key, value in data.items():
            lower_key = key.lower()
            if "pan" in lower_key and isinstance(value, str):
                masked_dict[key] = mask_pan(value)
            elif "aadhaar" in lower_key and isinstance(value, str):
                masked_dict[key] = mask_aadhaar(value)
            elif ("phone" in lower_key or "mobile" in lower_key) and isinstance(value, str):
                masked_dict[key] = mask_phone(value)
            elif ("account" in lower_key or "acc_no" in lower_key) and isinstance(value, (str, int)):
                masked_dict[key] = mask_bank_account(str(value))
            elif isinstance(value, (dict, list)):
                masked_dict[key] = mask_pii_dict(value)
            elif isinstance(value, str):
                masked_dict[key] = mask_pii_text(value)
            else:
                masked_dict[key] = value
        return masked_dict

    elif isinstance(data, list):
        return [mask_pii_dict(item) for item in data]

    return data
