def classify_issue(problem):
    text = (problem or "").casefold()

    keywords = {
        "Road & Transport": [
            "pothole", "road", "street", "traffic", "footpath",
            "bridge", "signal", "parking",
            "गड्ढा", "सड़क", "रस्ता", "खड्डा", "वाहतूक",
            "रस्त्यावर", "फुटपाथ", "ट्रॅफिक", "सिग्नल"
        ],
        "Water & Sanitation": [
            "water", "leakage", "pipeline", "drainage", "sewage",
            "flood", "पानी", "पाणी", "नल", "नळ", "पाइपलाइन",
            "गळती", "गटार", "नाली", "जलभराव", "पूर"
        ],
        "Waste Management": [
            "garbage", "waste", "dustbin", "trash", "dump",
            "कचरा", "गंदगी", "गंदा", "सफाई", "कूड़ा",
            "घाण", "स्वच्छता", "कचराकुंडी"
        ],
        "Electricity": [
            "electricity", "streetlight", "street light",
            "power cut", "blackout", "बिजली", "बत्ती",
            "लाईट", "वीज", "वीजपुरवठा", "दिवा", "पथदिवा"
        ],
        "Healthcare": [
            "hospital", "health", "medical", "clinic", "ambulance",
            "अस्पताल", "दवाखाना", "रुग्णालय", "आरोग्य",
            "रुग्णवाहिका", "डॉक्टर", "डॉक्टर"
        ],
        "Education": [
            "school", "college", "education", "teacher",
            "स्कूल", "विद्यालय", "शाळा", "महाविद्यालय",
            "शिक्षण", "शिक्षक"
        ],
        "Environment": [
            "park", "garden", "tree", "pollution", "noise",
            "उद्यान", "बाग", "पेड़", "झाड", "प्रदूषण",
            "ध्वनीप्रदूषण", "वायुप्रदूषण"
        ],
    }

    # Prefer the category with the strongest number of keyword matches.
    scores = {
        category: sum(1 for word in words if word in text)
        for category, words in keywords.items()
    }

    best_category = max(scores, key=scores.get)

    if scores[best_category] == 0:
        return "Other"

    return best_category


def analyze_severity(problem):
    text = (problem or "").casefold()

    high_keywords = [
        "death", "accident", "fire", "flood", "collapse",
        "danger", "dangerous", "emergency", "electric shock",
        "आग", "आग लागली", "अपघात", "दुर्घटना",
        "पूर", "बाढ़", "धोका", "धोकादायक",
        "वीज पडली", "करंट", "जीवघेणा", "जीवघेणे"
    ]

    medium_keywords = [
        "broken", "damaged", "leakage", "overflow", "blocked",
        "traffic", "not working", "garbage", "pothole",
        "टूटा", "खराब", "जाम", "कचरा", "खड्डा",
        "तुटले", "बंद आहे", "गळती", "तुंबले",
        "वाहतूक कोंडी", "पाणी साचले"
    ]

    if any(word in text for word in high_keywords):
        return "High"

    if any(word in text for word in medium_keywords):
        return "Medium"

    return "Low"


def calculate_priority(category, severity):
    severity_scores = {
        "Low": 30,
        "Medium": 60,
        "High": 90
    }

    category_bonus = {
        "Healthcare": 10,
        "Water & Sanitation": 10,
        "Electricity": 8,
        "Road & Transport": 5,
        "Waste Management": 4,
        "Environment": 4,
        "Education": 3,
        "Other": 0,
    }

    score = severity_scores.get(severity, 30)
    score += category_bonus.get(category, 0)

    return min(score, 100)