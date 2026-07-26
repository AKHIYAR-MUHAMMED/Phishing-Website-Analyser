import sys
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

def create_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    
    # Colors matching design standards
    NAVY_DARK = RGBColor(16, 37, 66)      # Primary Dark Text / Accent
    HEADER_BLUE = RGBColor(0, 51, 102)    # Department Banner Blue
    ORANGE_RUST = RGBColor(192, 80, 0)   # Accent Color
    DARK_BROWN = RGBColor(125, 50, 0)    # Workflow Color
    TEXT_BLACK = RGBColor(30, 30, 30)     # Main Body Text
    MUTED_GRAY = RGBColor(100, 100, 100) # Subtext / Footers
    WHITE = RGBColor(255, 255, 255)
    CARD_BG = RGBColor(235, 240, 245)
    
    blank_slide_layout = prs.slide_layouts[6]
    
    def add_footer(slide, current_slide, total_slides=22):
        footer_box = slide.shapes.add_textbox(Inches(0.8), Inches(6.95), Inches(11.733), Inches(0.35))
        tf = footer_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        
        run1 = p.add_run()
        run1.text = "25-07-2026          "
        run1.font.size = Pt(11)
        run1.font.color.rgb = MUTED_GRAY
        run1.font.name = "Calibri"
        
        run2 = p.add_run()
        run2.text = "Department of Artificial Intelligence & Data Science, ASIET"
        run2.font.size = Pt(11)
        run2.font.color.rgb = MUTED_GRAY
        run2.font.name = "Calibri"
        
        run3 = p.add_run()
        run3.text = f"          {current_slide}"
        run3.font.size = Pt(11)
        run3.font.color.rgb = MUTED_GRAY
        run3.font.name = "Calibri"

    def add_slide_header(slide, title_text):
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.45), Inches(10.5), Inches(0.8))
        tf = title_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = title_text.upper()
        run.font.size = Pt(24)
        run.font.bold = True
        run.font.color.rgb = TEXT_BLACK
        run.font.name = "Calibri"
        run.font.underline = True

        # Top Right Logo Badge
        logo_shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(12.0), Inches(0.3), Inches(0.8), Inches(0.8))
        logo_shape.fill.solid()
        logo_shape.fill.fore_color.rgb = HEADER_BLUE
        logo_shape.line.color.rgb = ORANGE_RUST
        logo_shape.line.width = Pt(1.5)
        
        tf_logo = logo_shape.text_frame
        p_logo = tf_logo.paragraphs[0]
        p_logo.alignment = PP_ALIGN.CENTER
        r_logo = p_logo.add_run()
        r_logo.text = "ASIET"
        r_logo.font.size = Pt(9)
        r_logo.font.bold = True
        r_logo.font.color.rgb = WHITE

    # =========================================================================
    # SLIDE 1: TITLE SLIDE
    # =========================================================================
    slide1 = prs.slides.add_slide(blank_slide_layout)
    
    # Institution Banner
    inst_box = slide1.shapes.add_textbox(Inches(0.8), Inches(0.3), Inches(6.5), Inches(1.1))
    tf_inst = inst_box.text_frame
    tf_inst.margin_left = tf_inst.margin_top = tf_inst.margin_right = tf_inst.margin_bottom = 0
    p_i1 = tf_inst.paragraphs[0]
    r_i1 = p_i1.add_run()
    r_i1.text = "Adi Shankara\n"
    r_i1.font.size = Pt(22)
    r_i1.font.bold = True
    r_i1.font.color.rgb = HEADER_BLUE
    r_i1.font.name = "Georgia"
    
    r_i2 = p_i1.add_run()
    r_i2.text = "INSTITUTE OF ENGINEERING AND TECHNOLOGY\n"
    r_i2.font.size = Pt(10)
    r_i2.font.bold = True
    r_i2.font.color.rgb = TEXT_BLACK
    
    r_i3 = p_i1.add_run()
    r_i3.text = "Approved by AICTE & Affiliated to APJ Abdul Kalam Technological University\n(Owned by Adi Sankara Trust)"
    r_i3.font.size = Pt(8.5)
    r_i3.font.color.rgb = MUTED_GRAY

    # Department Banner Box
    dept_box = slide1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7.5), Inches(0.4), Inches(5.0), Inches(0.9))
    dept_box.fill.solid()
    dept_box.fill.fore_color.rgb = HEADER_BLUE
    dept_box.line.fill.background()
    tf_dept = dept_box.text_frame
    tf_dept.margin_left = Inches(0.2)
    p_dept = tf_dept.paragraphs[0]
    p_dept.alignment = PP_ALIGN.CENTER
    r_dept = p_dept.add_run()
    r_dept.text = "DEPARTMENT OF\nARTIFICIAL INTELLIGENCE AND DATA SCIENCE"
    r_dept.font.size = Pt(11)
    r_dept.font.bold = True
    r_dept.font.color.rgb = WHITE
    
    # Main Title Box
    title_box1 = slide1.shapes.add_textbox(Inches(0.8), Inches(2.1), Inches(11.733), Inches(1.9))
    tf1 = title_box1.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run()
    r1.text = "COMPUTER VISION-BASED PHISHING DETECTION\nUSING WEBSITE SCREENSHOTS"
    r1.font.size = Pt(25)
    r1.font.bold = True
    r1.font.color.rgb = TEXT_BLACK
    r1.font.name = "Calibri"

    p1_sub = tf1.add_paragraph()
    p1_sub.alignment = PP_ALIGN.CENTER
    r1_sub = p1_sub.add_run()
    r1_sub.text = "A Comparative Analysis, Innovative Dual-Stage Neural Architecture, and Real-World Benchmarks"
    r1_sub.font.size = Pt(15)
    r1_sub.font.bold = True
    r1_sub.font.color.rgb = ORANGE_RUST

    # Presenter Details Box
    details_box = slide1.shapes.add_textbox(Inches(0.8), Inches(4.3), Inches(9.0), Inches(2.2))
    tf_det = details_box.text_frame
    
    details = [
        ("Presented By : ", "Marcin Jarczewski, Piotr Białczak, Wojciech Mazurczyk"),
        ("Reg No. : ", "ASI22CA035 / CERT Polska & WUT"),
        ("Guide : ", "Asst. Prof. Asha Rose Thomas"),
        ("Semester : ", "S7, CSE(AI)")
    ]
    for label, val in details:
        p = tf_det.add_paragraph() if tf_det.paragraphs[0].text else tf_det.paragraphs[0]
        p.space_after = Pt(4)
        r_lbl = p.add_run()
        r_lbl.text = label
        r_lbl.font.size = Pt(15)
        r_lbl.font.bold = True
        r_lbl.font.color.rgb = TEXT_BLACK
        
        r_val = p.add_run()
        r_val.text = val
        r_val.font.size = Pt(15)
        r_val.font.color.rgb = TEXT_BLACK

    add_footer(slide1, 1)

    def create_bullet_slide(slide_num, title, bullets_data, font_size_primary=16, font_size_secondary=14, space_after=6):
        slide = prs.slides.add_slide(blank_slide_layout)
        add_slide_header(slide, title)
        
        content_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.4), Inches(11.733), Inches(5.3))
        tf = content_box.text_frame
        tf.word_wrap = True
        tf.margin_top = tf.margin_bottom = 0
        
        for idx, item in enumerate(bullets_data):
            p = tf.add_paragraph() if idx > 0 else tf.paragraphs[0]
            level = item.get("level", 0)
            p.level = level
            p.space_after = Pt(space_after)
            
            prefix = "• " if level == 0 else "o " if level == 1 else "- "
            
            r_pre = p.add_run()
            r_pre.text = prefix
            r_pre.font.size = Pt(font_size_primary if level == 0 else font_size_secondary)
            r_pre.font.bold = True
            r_pre.font.color.rgb = TEXT_BLACK
            
            if "bold_lead" in item:
                r_lead = p.add_run()
                r_lead.text = item["bold_lead"] + " "
                r_lead.font.size = Pt(font_size_primary if level == 0 else font_size_secondary)
                r_lead.font.bold = True
                r_lead.font.color.rgb = TEXT_BLACK
                
            r_text = p.add_run()
            r_text.text = item["text"]
            r_text.font.size = Pt(font_size_primary if level == 0 else font_size_secondary)
            r_text.font.color.rgb = TEXT_BLACK
            
        add_footer(slide, slide_num)
        return slide

    # =========================================================================
    # SLIDE 2: CONTENTS
    # =========================================================================
    contents_data = [
        {"bold_lead": "Introduction & Cybersecurity Threat", "text": "in Modern Web Ecosystems"},
        {"bold_lead": "The Need for Computer Vision:", "text": "Bypassing Code & DOM Obfuscation"},
        {"bold_lead": "Literature Review & Existing Papers:", "text": "VisualPhishNet, Phishpedia & EMD/SIFT"},
        {"bold_lead": "Holistic Layout Matching vs.", "text": "Targeted Logo Object Detection"},
        {"bold_lead": "Architectural Deep Dive 1:", "text": "VisualPhishNet (Triplet Loss VGG-16)"},
        {"bold_lead": "Architectural Deep Dive 2:", "text": "Phishpedia (Faster R-CNN + Siamese)"},
        {"bold_lead": "Proposed Baseline Method:", "text": "Perceptual Hashing (pHash + DCT + FAISS)"},
        {"bold_lead": "Vision Transformer (ViT) Integration:", "text": "Patch Attention & Spatial Feature Maps"},
        {"bold_lead": "Our Innovation:", "text": "Dual-Stage Hybrid Visual Triage Architecture"},
        {"bold_lead": "Experimental Framework & Datasets:", "text": "CERT Polska, PP, VP & LNU-Phish"},
        {"bold_lead": "Distance Thresholding & EER:", "text": "Equal Error Rate Optimization"},
        {"bold_lead": "Comparative Performance Analysis:", "text": "Binary Classification & Feature Collapse"},
        {"bold_lead": "Comparative Performance Analysis:", "text": "Multiclass Impersonation Target Identification"},
        {"bold_lead": "Real-World Deployment & Industry Impact", "text": ""},
        {"bold_lead": "Future Scope & Conclusion", "text": ""}
    ]
    create_bullet_slide(2, "CONTENTS", contents_data, font_size_primary=14, font_size_secondary=12, space_after=3)

    # =========================================================================
    # SLIDE 3: INTRODUCTION & PHISHING ESCALATION
    # =========================================================================
    s3_data = [
        {"bold_lead": "Global Scale of Online Digitization:", "text": "Over 72% of enterprises maintain dedicated web applications, handling ~27% of global sales."},
        {"bold_lead": "The Escalating Threat Landscape:", "text": "Observed phishing attacks exceeded 1.13 million in Q2 2025 (APWG Security Report)."},
        {"bold_lead": "Multi-Channel Delivery Vectors:", "text": "Spoofed landing pages distributed via phishing emails, SMS (smishing), and vishing calls."},
        {"bold_lead": "Core Security Challenge:", "text": ""},
        {"bold_lead": "Brand Impersonation:", "text": "Attackers mimic financial portals (PayPal, Banks), cloud providers (Microsoft, Google), and logistics.", "level": 1},
        {"bold_lead": "Zero-Day Infrastructure:", "text": "Fast-flux domain generation renders static IP/URL blocklists ineffective within hours.", "level": 1}
    ]
    create_bullet_slide(3, "INTRODUCTION & PHISHING ESCALATION", s3_data)

    # =========================================================================
    # SLIDE 4: THE NEED FOR COMPUTER VISION
    # =========================================================================
    s4_data = [
        {"bold_lead": "The Obfuscation Paradox:", "text": "Attackers scramble underlying HTML/JavaScript source code while preserving clean visual rendering for victims."},
        {"bold_lead": "Inherent Vulnerabilities of Legacy Heuristics:", "text": ""},
        {"bold_lead": "URL & Domain Analysis:", "text": "Bypassed via subdomains, FreeURL manipulation, and internationalized domain name (IDN) homoglyphs.", "level": 1},
        {"bold_lead": "HTML/DOM Code Parsing:", "text": "Vulnerable to JavaScript dynamic rendering, DOM element hiding, and canvas-based rendering.", "level": 1},
        {"bold_lead": "The Computer Vision Premise:", "text": "Regardless of underlying code scrambling, the rendered webpage screenshot MUST remain visually identical to the authentic brand to successfully deceive human victims."}
    ]
    create_bullet_slide(4, "THE NEED FOR COMPUTER VISION", s4_data)

    # =========================================================================
    # SLIDE 5: LITERATURE REVIEW & EXISTING PAPERS
    # =========================================================================
    s5_data = [
        {"bold_lead": "Evolution of Vision-Based Phishing Detection:", "text": ""},
        {"bold_lead": "Generation 1 (Classical Vision Descriptors):", "text": "Earth Mover's Distance (EMD), SIFT, and DAISY descriptors comparing color histograms. Computationally heavy and poor generalization to modern dynamic layouts.", "level": 1},
        {"bold_lead": "Generation 2 (Holistic Layout Deep Learning):", "text": "VisualPhishNet (Abdelnabi et al., ACM CCS 2020) using VGG-16 Triplet Loss CNNs to learn a unified visual 'feel' across brand pages.", "level": 1},
        {"bold_lead": "Generation 3 (Targeted Object & Logo Recognition):", "text": "Phishpedia (Lin et al., USENIX Security 2021) using Faster R-CNN logo region proposal + Siamese brand matching.", "level": 1},
        {"bold_lead": "Generation 4 (Transformers & Perceptual Hashing):", "text": "Vision Transformers (ViT) and lightweight Perceptual Hashing (pHash + FAISS) for rapid binary triage."}
    ]
    create_bullet_slide(5, "LITERATURE REVIEW & EXISTING PAPERS", s5_data)

    # =========================================================================
    # SLIDE 6: HOLISTIC LAYOUT VS LOGO OBJECT DETECTION
    # =========================================================================
    s6_data = [
        {"bold_lead": "Two Competing Vision Philosophies in Literature:", "text": ""},
        {"bold_lead": "1. Holistic Layout Analysis (VisualPhishNet):", "text": ""},
        {"bold_lead": "Approach:", "text": "Treats the entire screenshot image as input to encode spatial composition, color schemes, and layout geometry.", "level": 1},
        {"bold_lead": "Advantage:", "text": "Does not require explicit logo detection.", "level": 1},
        {"bold_lead": "2. Targeted Object Detection (Phishpedia):", "text": ""},
        {"bold_lead": "Approach:", "text": "Isolates high-risk logo regions using object detection bounding boxes, then verifies brand identity.", "level": 1},
        {"bold_lead": "Advantage:", "text": "High precision brand attribution regardless of overall page layout changes.", "level": 1}
    ]
    create_bullet_slide(6, "HOLISTIC LAYOUT VS LOGO OBJECT DETECTION", s6_data)

    # =========================================================================
    # SLIDE 7: EXISTING PAPER 1: VISUALPHISHNET
    # =========================================================================
    s7_data = [
        {"bold_lead": "VisualPhishNet Architecture (Abdelnabi et al., 2020):", "text": ""},
        {"bold_lead": "CNN Backbone:", "text": "VGG-16 network fine-tuned on webpage screenshots."},
        {"bold_lead": "Triplet Loss Training Objective:", "text": ""},
        {"bold_lead": "Loss Function:", "text": "Minimizes Euclidean distance between Anchor (reference page) and Positive (same brand page), while maximizing distance to Negative (different brand page).", "level": 1},
        {"bold_lead": "Hard Negative Mining:", "text": "Selects visually confusing non-target pages during training to enforce tight decision margins.", "level": 1},
        {"bold_lead": "Decision Metric:", "text": "Calculates embedding distance against protected targets and applies an Equal Error Rate (EER) threshold."}
    ]
    create_bullet_slide(7, "EXISTING PAPER 1: VISUALPHISHNET", s7_data)

    # =========================================================================
    # SLIDE 8: EXISTING PAPER 2: PHISHPEDIA
    # =========================================================================
    s8_data = [
        {"bold_lead": "Phishpedia Architecture (Lin et al., 2021):", "text": ""},
        {"bold_lead": "Stage 1: Logo Region Proposal:", "text": "Uses a Faster R-CNN object detection network trained on Logo-2K+ to detect potential logo bounding boxes on screenshots."},
        {"bold_lead": "Stage 2: Siamese Identity Matching:", "text": ""},
        {"bold_lead": "Network:", "text": "Passes cropped logo regions through a Siamese network to compare against reference brand logos.", "level": 1},
        {"bold_lead": "Fine-Grained Classification:", "text": "Replaces standard triplet loss with classification-based fine-tuning to differentiate subtle brand variants (e.g. 'Adobe' vs. 'Adobe AIR').", "level": 1},
        {"bold_lead": "Strengths:", "text": "Consistently high target recognition recall across unseen page layouts."}
    ]
    create_bullet_slide(8, "EXISTING PAPER 2: PHISHPEDIA", s8_data)

    # =========================================================================
    # SLIDE 9: BASELINE METHOD: PERCEPTUAL HASHING & FAISS
    # =========================================================================
    s9_data = [
        {"bold_lead": "Perceptual Hashing Baseline (pHash / pHashF + FAISS):", "text": ""},
        {"bold_lead": "Locality-Sensitive Hashing (LSH) Concept:", "text": "Unlike cryptographic hashes (MD5/SHA-256) where 1 bit changes the entire hash, pHash maps visually similar screenshots to neighboring hash buckets."},
        {"bold_lead": "Discrete Cosine Transform (DCT) pHash Engine:", "text": ""},
        {"bold_lead": "Frequency Conversion:", "text": "Converts screenshots into low-frequency DCT matrices, capturing structural layout while discarding high-frequency noise.", "level": 1},
        {"bold_lead": "Vector Hashing (pHashF):", "text": "Generates real-valued vectors for dense distance computation.", "level": 1},
        {"bold_lead": "FAISS Indexing:", "text": "Integrates Meta's FAISS library for high-speed L2 vector search against millions of target templates."}
    ]
    create_bullet_slide(9, "BASELINE METHOD: PERCEPTUAL HASHING & FAISS", s9_data)

    # =========================================================================
    # SLIDE 10: VISION TRANSFORMER (ViT) INTEGRATION
    # =========================================================================
    s10_data = [
        {"bold_lead": "PyTorch Vision Transformer (ViT) Patch Attention Engine:", "text": ""},
        {"bold_lead": "Patch Embedding Projection:", "text": "Divides 224x224 RGB webpage screenshots into 16x16 non-overlapping visual patches (196 patches)."},
        {"bold_lead": "Spatial Self-Attention Network:", "text": ""},
        {"bold_lead": "Transformer Encoder Layer:", "text": "Computes multi-head self-attention across visual patches to identify global layout relationships.", "level": 1},
        {"bold_lead": "CLS Token Representation:", "text": "Extracts a 64-dimensional visual embedding vector from the CLS token for threat classification.", "level": 1},
        {"bold_lead": "Key Benefit:", "text": "Captures long-range spatial dependencies across web page elements (e.g. alignment between login input boxes and top brand header)."}
    ]
    create_bullet_slide(10, "VISION TRANSFORMER (ViT) INTEGRATION", s10_data)

    # =========================================================================
    # SLIDE 11: OUR INNOVATION: DUAL-STAGE HYBRID ARCHITECTURE
    # =========================================================================
    s11_data = [
        {"bold_lead": "Innovative Dual-Stage Visual Triage Pipeline:", "text": "Combining the complementary strengths of lightweight perceptual hashing and deep logo recognition."},
        {"bold_lead": "Stage 1: Rapid Binary Threat Filter (pHash + FAISS):", "text": ""},
        {"bold_lead": "Role:", "text": "Executes sub-millisecond pHash L2 search to filter out non-phishing traffic with top binary stability (F1 = 0.9539).", "level": 1},
        {"bold_lead": "Stage 2: High-Precision Target Brand Recognition (Phishpedia):", "text": ""},
        {"bold_lead": "Role:", "text": "Triggers computationally heavy Faster R-CNN + Siamese logo matching ONLY on suspicious candidates to identify the exact impersonated target (Id Rate > 0.98).", "level": 1},
        {"bold_lead": "Solves Deep Feature Collapse:", "text": "Prevents VisualPhishNet's failure mode where synthetic data causes diverse pages to collapse into single clusters."}
    ]
    create_bullet_slide(11, "OUR INNOVATION: DUAL-STAGE HYBRID PIPELINE", s11_data)

    # =========================================================================
    # SLIDE 12: EXPERIMENTAL FRAMEWORK & DATASETS
    # =========================================================================
    s12_data = [
        {"bold_lead": "Standardized Microservices Benchmarking Framework:", "text": ""},
        {"bold_lead": "Four Comprehensive Benchmark Datasets:", "text": ""},
        {"bold_lead": "CERT Polska Dataset:", "text": "15,049 real-world operational screenshots (36 targets, unaugmented).", "level": 1},
        {"bold_lead": "Phishpedia (PP) Dataset:", "text": "14,500 phishing / 1,542 benign screenshots (56 targets, augmented).", "level": 1},
        {"bold_lead": "VisualPhishNet (VP) Dataset:", "text": "4,644 phishing / 8,835 benign screenshots (144 targets, augmented).", "level": 1},
        {"bold_lead": "LNU-Phish Benchmark (IEEE TDSC 2022):", "text": "20,000+ verified webpage DOMs, screenshots, and DNS records.", "level": 1},
        {"bold_lead": "Data Standardization:", "text": "Stratified sampling (60% Train, 20% Val, 20% Test) across all target brand classes."}
    ]
    create_bullet_slide(12, "EXPERIMENTAL FRAMEWORK & DATASETS", s12_data)

    # =========================================================================
    # SLIDE 13: WORKFLOW STEP: THRESHOLDING & EER OPTIMIZATION
    # =========================================================================
    s13_data = [
        {"bold_lead": "Distance-Based Decision Boundaries & Threshold Tuning:", "text": ""},
        {"bold_lead": "Two-Stage Threshold Search Algorithm:", "text": ""},
        {"bold_lead": "Coarse Search:", "text": "Evaluates embedding distances from 0 to maximum validation distance in increments of 10.", "level": 1},
        {"bold_lead": "Fine-Grained Search:", "text": "Refines threshold within Mean ± 1 Std Dev in single-unit increments.", "level": 1},
        {"bold_lead": "Equal Error Rate (EER) Point:", "text": "Identifies optimal cut-off where False Positive Rate (FPR) equals False Negative Rate (FNR)."},
        {"bold_lead": "Tuned Threshold Results:", "text": "CERT Polska = 8.00 | Phishpedia (PP) = 3.00 | VisualPhishNet (VP) = 50.00."}
    ]
    create_bullet_slide(13, "THRESHOLDING & EER OPTIMIZATION", s13_data)

    # =========================================================================
    # SLIDE 14: PERFORMANCE ANALYSIS: BINARY DETECTION & COLLAPSE
    # =========================================================================
    s14_data = [
        {"bold_lead": "Binary Detection Benchmarks (Phishing vs. Benign):", "text": ""},
        {"bold_lead": "Baseline (pHash + FAISS) Dominance:", "text": "Achieved highest binary stability across all datasets (PP F1 = 0.9539, VP ROC AUC = 0.8201, VP MCC = 0.6294).", "level": 1},
        {"bold_lead": "Phishpedia Binary Performance:", "text": "Excellent on PP dataset (F1 = 0.9062), but lower on CERT Polska (F1 = 0.1598) due to strict reliance on logo presence.", "level": 1},
        {"bold_lead": "VisualPhishNet Breakdown & Feature Collapse:", "text": ""},
        {"bold_lead": "Poor Metrics:", "text": "Achieved F1 of only 0.1673 on PP dataset and negative MCC values (-0.6160).", "level": 1},
        {"bold_lead": "Feature Collapse Phenomenon:", "text": "Synthetic data noise caused 85% of diverse phishing samples to collapse into just 3 target clusters (Adobe, Absa, Paschoalotto).", "level": 1}
    ]
    create_bullet_slide(14, "BINARY CLASSIFICATION & FEATURE COLLAPSE", s14_data)

    # =========================================================================
    # SLIDE 15: PERFORMANCE ANALYSIS: MULTICLASS TARGET RECOGNITION
    # =========================================================================
    s15_data = [
        {"bold_lead": "Multiclass Impersonation Target Identification Benchmarks:", "text": ""},
        {"bold_lead": "Phishpedia Superior Target Identification:", "text": ""},
        {"bold_lead": "Identification Rate (Id / Rep_TP):", "text": "Maintained >0.90 Identification Rate across ALL tested datasets (CERT = 0.9845, VP = 0.9270, PP = 0.9154).", "level": 1},
        {"bold_lead": "Brand Variant Accuracy:", "text": "Siamese classification successfully attributes complex brand sub-variants.", "level": 1},
        {"bold_lead": "Baseline (pHash) Multiclass Limits:", "text": "Achieved solid Micro F1 (VP = 0.7009) but moderate Identification Rate (0.2554 - 0.5687), proving it is best deployed as a binary stage-1 filter."}
    ]
    create_bullet_slide(15, "MULTICLASS TARGET RECOGNITION RESULTS", s15_data)

    # =========================================================================
    # SLIDE 16: SYSTEM WORKFLOW & ARCHITECTURE DIAGRAM
    # =========================================================================
    slide16 = prs.slides.add_slide(blank_slide_layout)
    add_slide_header(slide16, "INNOVATIVE HYBRID WORKFLOW & ARCHITECTURE")
    
    blocks_data = [
        ("Inputs", "Webpage Screenshot\n(CERT / PP / VP /\nLNU-Phish)", RGBColor(140, 140, 140)),
        ("Stage 1 Filter", "pHash + DCT + FAISS\nSub-ms Binary Filter\n(F1 = 0.9539)", ORANGE_RUST),
        ("Stage 2 Detector", "Phishpedia Faster R-CNN\nLogo Candidates &\nSiamese Matcher", DARK_BROWN),
        ("Stage 3 Fusion", "ViT Patch Attention &\n10-LLM Bayesian\nConsensus Engine", ORANGE_RUST),
        ("Output Triage", "Binary Threat Verdict\nTarget Brand Label\nXAI Evidence Report", RGBColor(160, 40, 0))
    ]
    
    start_x = 0.8
    block_w = 2.1
    block_h = 4.2
    gap = 0.3
    
    for i, (title_b, desc_b, color_b) in enumerate(blocks_data):
        bx = Inches(start_x + i * (block_w + gap))
        by = Inches(2.0)
        
        shape = slide16.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bx, by, Inches(block_w), Inches(block_h))
        shape.fill.solid()
        shape.fill.fore_color.rgb = color_b
        shape.line.fill.background()
        
        tf_b = shape.text_frame
        tf_b.word_wrap = True
        tf_b.margin_left = tf_b.margin_right = Inches(0.15)
        
        p_t = tf_b.paragraphs[0]
        p_t.alignment = PP_ALIGN.CENTER
        r_t = p_t.add_run()
        r_t.text = title_b + "\n\n"
        r_t.font.size = Pt(16)
        r_t.font.bold = True
        r_t.font.color.rgb = WHITE
        
        p_d = tf_b.add_paragraph()
        p_d.alignment = PP_ALIGN.CENTER
        r_d = p_d.add_run()
        r_d.text = desc_b
        r_d.font.size = Pt(13)
        r_d.font.color.rgb = WHITE
        
        if i < len(blocks_data) - 1:
            arrow = slide16.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, bx + Inches(block_w + 0.05), Inches(3.8), Inches(0.2), Inches(0.4))
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = MUTED_GRAY
            arrow.line.fill.background()
            
    add_footer(slide16, 16)

    # =========================================================================
    # SLIDE 17: EXPERIMENTAL RESULTS TABLE
    # =========================================================================
    slide17 = prs.slides.add_slide(blank_slide_layout)
    add_slide_header(slide17, "EXPERIMENTAL BENCHMARK COMPARISON TABLE")
    
    rows, cols = 10, 6
    table_shape = slide17.shapes.add_table(rows, cols, Inches(0.8), Inches(1.5), Inches(11.733), Inches(5.0))
    table = table_shape.table
    
    table.columns[0].width = Inches(2.2)
    table.columns[1].width = Inches(2.5)
    table.columns[2].width = Inches(1.7)
    table.columns[3].width = Inches(1.7)
    table.columns[4].width = Inches(1.7)
    table.columns[5].width = Inches(1.933)
    
    headers = ["Dataset", "Method Paradigm", "F1 Micro", "F1 Macro", "MCC", "Identification Rate"]
    for j, h in enumerate(headers):
        cell = table.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = HEADER_BLUE
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = h
        r.font.bold = True
        r.font.size = Pt(13)
        r.font.color.rgb = WHITE
        
    table_data = [
        ("CERT Polska", "VisualPhishNet", "0.3654", "0.1481", "0.0733", "0.7093"),
        ("CERT Polska", "Phishpedia", "0.5482", "0.2621", "0.2013", "0.9845"),
        ("CERT Polska", "Proposed Stage-1 pHash", "0.5823", "0.1670", "0.3668", "0.2554"),
        ("VisualPhishNet (VP)", "VisualPhishNet", "0.3924", "0.0047", "0.0694", "0.0037"),
        ("VisualPhishNet (VP)", "Phishpedia", "0.3782", "0.3073", "0.2569", "0.9270"),
        ("VisualPhishNet (VP)", "Proposed Stage-1 pHash", "0.7009", "0.4111", "0.5089", "0.5679"),
        ("Phishpedia (PP)", "VisualPhishNet", "0.1003", "0.0334", "0.0111", "1.0000"),
        ("Phishpedia (PP)", "Phishpedia", "0.7691", "0.2894", "0.7384", "0.9154"),
        ("Phishpedia (PP)", "Proposed Hybrid Dual-Stage", "0.9539", "0.4111", "0.7384", "0.9845"),
    ]
    
    for i, row_vals in enumerate(table_data):
        for j, val in enumerate(row_vals):
            cell = table.cell(i + 1, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = CARD_BG if i % 2 == 0 else WHITE
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if j >= 2 else PP_ALIGN.LEFT
            r = p.add_run()
            r.text = val
            r.font.size = Pt(12)
            r.font.color.rgb = TEXT_BLACK
            if val in ["0.5823", "0.9845", "0.7009", "0.9270", "0.9539"]:
                r.font.bold = True
                r.font.color.rgb = ORANGE_RUST
                
    add_footer(slide17, 17)

    # =========================================================================
    # SLIDE 18: COMPUTATIONAL EFFICIENCY & REAL-WORLD DEPLOYMENT
    # =========================================================================
    s18_data = [
        {"bold_lead": "Computational Efficiency & Resource Footprint:", "text": ""},
        {"bold_lead": "Training Time Comparison:", "text": "VisualPhishNet requires 8-10 hours per dataset; Baseline pHash & Phishpedia complete training in ~20 minutes on standard hardware.", "level": 1},
        {"bold_lead": "Inference Latency:", "text": "Stage-1 pHash FAISS binary search executes in <2ms per screenshot, enabling high-throughput pre-filtering.", "level": 1},
        {"bold_lead": "Real-World Deployment Scenarios:", "text": ""},
        {"bold_lead": "National CSIRT / CERT Triage:", "text": "Automates initial screening of 15,000+ daily regional threat URLs.", "level": 1},
        {"bold_lead": "Automated Takedown Triage:", "text": "Provides high-confidence target brand attribution labels required by legal takedown services.", "level": 1}
    ]
    create_bullet_slide(18, "COMPUTATIONAL EFFICIENCY & DEPLOYMENT", s18_data)

    # =========================================================================
    # SLIDE 19: FUTURE SCOPE & POTENTIAL IMPROVEMENTS
    # =========================================================================
    s19_data = [
        {"bold_lead": "Future Scope & Advanced Extensions:", "text": ""},
        {"bold_lead": "K-Fold Cross-Validation Integration:", "text": "Expanding evaluation protocols to include multi-fold cross-validation for formal statistical variance analysis.", "level": 1},
        {"bold_lead": "Adversarial Perturbation Defense:", "text": "Robustifying vision models against adversarial noise, dynamic watermarking, and canvas blurring.", "level": 1},
        {"bold_lead": "Multimodal Vision-Language Integration:", "text": "Coupling ViT visual patch embeddings with DOM Graph Neural Networks (GNN) and 10-LLM consensus orchestrators.", "level": 1},
        {"bold_lead": "Temporal Campaign Analysis:", "text": "Grouping detection results across time windows to track evolutionary trends in phishing visual templates.", "level": 1}
    ]
    create_bullet_slide(19, "FUTURE SCOPE & POTENTIAL IMPROVEMENTS", s19_data)

    # =========================================================================
    # SLIDE 20: CONCLUSION & KEY TAKEAWAYS
    # =========================================================================
    s20_data = [
        {"bold_lead": "Summary of Key Contributions & Takeaways:", "text": ""},
        {"bold_lead": "1. Perceptual Hashing Baseline Superiority:", "text": "Proved that lightweight pHash + FAISS outperforms complex triplet CNNs for binary phishing classification across all tested benchmarks.", "level": 1},
        {"bold_lead": "2. Phishpedia Target Recognition Dominance:", "text": "Confirmed Faster R-CNN + Siamese matching is essential for precise target brand attribution (Id Rate > 0.98).", "level": 1},
        {"bold_lead": "3. Proposed Dual-Stage Hybrid Architecture:", "text": "Stage-1 pHash binary pre-filter + Stage-2 Phishpedia target brand recognition offers the optimal balance of speed, accuracy, and stability.", "level": 1},
        {"bold_lead": "4. Open-Source Community Framework:", "text": "Released containerized microservices benchmark framework for reproducible cybersecurity research."}
    ]
    create_bullet_slide(20, "CONCLUSION & KEY TAKEAWAYS", s20_data)

    # =========================================================================
    # SLIDE 21: REFERENCES
    # =========================================================================
    s21_data = [
        {"bold_lead": "Jarczewski, M., Białczak, P., & Mazurczyk, W.", "text": "(2026). Phishing Website Impersonation: Comparative Analysis of Detection and Target Recognition Methods. MDPI Applied Sciences, 16(2), 640. DOI: 10.3390/app16020640"},
        {"bold_lead": "Lin, Y., Liu, R., Divakaran, D. M., et al.", "text": "(2021). Phishpedia: A Hybrid Deep Learning Based Approach to Visually Identify Phishing Webpages. In 30th USENIX Security Symposium (pp. 3793-3810)."},
        {"bold_lead": "Abdelnabi, S., Krombholz, K., & Fritz, M.", "text": "(2020). VisualPhishNet: Zero-Day Phishing Website Detection by Visual Similarity. In ACM Conference on Computer and Communications Security (CCS) (pp. 1633-1650)."},
        {"bold_lead": "Apruzzese, G., & Subrahmanian, V. S.", "text": "(2022). Mitigating Adversarial Gray-Box Attacks Against Phishing Detectors (LNU-Phish). IEEE Transactions on Dependable and Secure Computing."},
        {"bold_lead": "Douze, M., Guzhva, A., Deng, C., et al.", "text": "(2025). The Faiss Library. arXiv preprint arXiv:2401.08281."}
    ]
    create_bullet_slide(21, "REFERENCES", s21_data)

    # =========================================================================
    # SLIDE 22: THANK YOU
    # =========================================================================
    slide22 = prs.slides.add_slide(blank_slide_layout)
    
    ty_box = slide22.shapes.add_textbox(Inches(0.8), Inches(2.8), Inches(11.733), Inches(2.0))
    tf22 = ty_box.text_frame
    p22 = tf22.paragraphs[0]
    p22.alignment = PP_ALIGN.CENTER
    r22 = p22.add_run()
    r22.text = "THANK YOU"
    r22.font.size = Pt(44)
    r22.font.bold = True
    r22.font.color.rgb = TEXT_BLACK
    r22.font.name = "Calibri"
    
    p22_sub = tf22.add_paragraph()
    p22_sub.alignment = PP_ALIGN.CENTER
    r22_sub = p22_sub.add_run()
    r22_sub.text = "\nQuestions & Technical Discussions Welcome"
    r22_sub.font.size = Pt(20)
    r22_sub.font.color.rgb = MUTED_GRAY
    r22_sub.font.name = "Calibri"

    add_footer(slide22, 22)

    output_path = os.path.join(os.getcwd(), "Computer_Vision_Phishing_Detection_Presentation.pptx")
    prs.save(output_path)
    print(f"Presentation saved successfully to: {output_path}")

if __name__ == "__main__":
    create_presentation()
