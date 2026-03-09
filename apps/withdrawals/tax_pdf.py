"""
withdrawals/tax_pdf.py
Generates a professional South African withholding tax certificate PDF
using reportlab. Returns the PDF as bytes ready to save to a FileField.
"""
import io
from datetime import datetime
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import (
    HexColor, white, black
)
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors


# ── Brand colours ────────────────────────────────────────────────
NAVY        = HexColor('#0a1f44')
NAVY_DARK   = HexColor('#03071e')
GOLD        = HexColor('#e08900')
GOLD_LIGHT  = HexColor('#fac660')
GRAY_TEXT   = HexColor('#4a5568')
GRAY_LIGHT  = HexColor('#e8f0f9')
GRAY_BORDER = HexColor('#c8d6e8')
GREEN       = HexColor('#198754')


def _draw_rounded_rect(c, x, y, w, h, radius, fill_color=None, stroke_color=None):
    """Draw a rectangle with rounded corners on the canvas."""
    p = c.beginPath()
    p.moveTo(x + radius, y)
    p.lineTo(x + w - radius, y)
    p.arcTo(x + w - radius, y, x + w, y + radius, -90, 90)
    p.lineTo(x + w, y + h - radius)
    p.arcTo(x + w - radius, y + h - radius, x + w, y + h, 0, 90)
    p.lineTo(x + radius, y + h)
    p.arcTo(x, y + h - radius, x + radius, y + h, 90, 90)
    p.lineTo(x, y + radius)
    p.arcTo(x, y, x + radius, y + radius, 180, 90)
    p.close()
    if fill_color:
        c.setFillColor(fill_color)
    if stroke_color:
        c.setStrokeColor(stroke_color)
        c.setLineWidth(0.5)
    if fill_color and stroke_color:
        c.drawPath(p, fill=1, stroke=1)
    elif fill_color:
        c.drawPath(p, fill=1, stroke=0)
    else:
        c.drawPath(p, fill=0, stroke=1)


def generate_tax_certificate(withdrawal) -> bytes:
    """
    Generate a professional tax withholding certificate for a withdrawal.
    Returns PDF as bytes.
    """
    buffer = io.BytesIO()
    W, H = A4  # 595.27 x 841.89 pts
    MARGIN = 20 * mm

    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Tax Certificate — {withdrawal.reference}")
    c.setAuthor("InvestZA Platform")
    c.setSubject("Withholding Tax Certificate")

    user    = withdrawal.user
    now     = datetime.now()
    tax_yr  = f"{now.year - 1}/{now.year}" if now.month < 3 else f"{now.year}/{now.year + 1}"
    cert_no = f"TC-{withdrawal.reference}-{now.strftime('%Y%m%d')}"
    net_amt = withdrawal.amount - withdrawal.fee
    # Standard SA dividend withholding tax 20% for illustrative purposes
    tax_rate    = Decimal('0.20')
    tax_withheld = (withdrawal.amount * tax_rate).quantize(Decimal('0.01'))

    # ── BACKGROUND ───────────────────────────────────────────────
    c.setFillColor(HexColor('#f5f8fd'))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # ── HEADER BAND ──────────────────────────────────────────────
    c.setFillColor(NAVY_DARK)
    c.rect(0, H - 52 * mm, W, 52 * mm, fill=1, stroke=0)

    # Gold accent bar at very top
    c.setFillColor(GOLD)
    c.rect(0, H - 3 * mm, W, 3 * mm, fill=1, stroke=0)

    # Logo box
    lx, ly = MARGIN, H - 42 * mm
    _draw_rounded_rect(c, lx, ly, 16 * mm, 16 * mm, 2 * mm, fill_color=GOLD)
    c.setFillColor(NAVY_DARK)
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(lx + 8 * mm, ly + 5 * mm, 'IZ')

    # Platform name
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 18)
    c.drawString(lx + 20 * mm, ly + 9 * mm, 'InvestZA')
    c.setFont('Helvetica', 9)
    c.setFillColor(GOLD_LIGHT)
    c.drawString(lx + 20 * mm, ly + 3.5 * mm, 'South African Multi-Asset Investment Platform')

    # Document title (right-aligned in header)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 14)
    c.drawRightString(W - MARGIN, ly + 9 * mm, 'WITHHOLDING TAX CERTIFICATE')
    c.setFont('Helvetica', 8)
    c.setFillColor(GOLD_LIGHT)
    c.drawRightString(W - MARGIN, ly + 3.5 * mm, f'Tax Year: {tax_yr}  |  Certificate No: {cert_no}')

    # ── VERIFIED STAMP / BADGE ───────────────────────────────────
    bx = W - MARGIN - 32 * mm
    by = H - 52 * mm - 22 * mm
    _draw_rounded_rect(c, bx, by, 32 * mm, 14 * mm, 2 * mm,
                       fill_color=HexColor('#d1e7dd'), stroke_color=GREEN)
    c.setFillColor(GREEN)
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(bx + 16 * mm, by + 5.5 * mm, '✓  ISSUED & VERIFIED')

    # ── CERT INFO ROW (issued date / ref) ───────────────────────
    iy = H - 52 * mm - 12 * mm
    c.setFillColor(GRAY_TEXT)
    c.setFont('Helvetica', 8)
    c.drawString(MARGIN, iy, f'Issue Date:  {now.strftime("%d %B %Y")}')
    c.drawString(MARGIN + 60 * mm, iy, f'Reference:  {withdrawal.reference}')
    c.drawString(MARGIN + 120 * mm, iy, f'Tax Code:  {withdrawal.tax_code}')

    # ── SECTION: TAXPAYER DETAILS ─────────────────────────────────
    sy = H - 52 * mm - 30 * mm
    _draw_rounded_rect(c, MARGIN, sy - 42 * mm, W - 2 * MARGIN, 42 * mm, 2 * mm,
                       fill_color=white, stroke_color=GRAY_BORDER)

    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(MARGIN + 4 * mm, sy - 6 * mm, 'TAXPAYER DETAILS')
    # gold underline
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.line(MARGIN + 4 * mm, sy - 7.5 * mm, MARGIN + 40 * mm, sy - 7.5 * mm)

    fields = [
        ('Full Name',       user.get_full_name()),
        ('Email Address',   user.email),
        ('Phone Number',    user.phone_number or '—'),
        ('SA ID / Passport', user.id_number or '—'),
        ('Account Number',  user.wallet.account_number if hasattr(user, 'wallet') else '—'),
    ]
    col1_x = MARGIN + 4 * mm
    col2_x = MARGIN + 50 * mm
    row_y   = sy - 14 * mm

    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(GRAY_TEXT)
    for label, value in fields:
        c.setFont('Helvetica', 7)
        c.setFillColor(GRAY_TEXT)
        c.drawString(col1_x, row_y, label)
        c.setFont('Helvetica-Bold', 8)
        c.setFillColor(NAVY)
        c.drawString(col2_x, row_y, str(value))
        row_y -= 6.5 * mm

    # ── SECTION: TRANSACTION DETAILS ─────────────────────────────
    ty = sy - 48 * mm
    _draw_rounded_rect(c, MARGIN, ty - 50 * mm, W - 2 * MARGIN, 50 * mm, 2 * mm,
                       fill_color=white, stroke_color=GRAY_BORDER)

    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(MARGIN + 4 * mm, ty - 6 * mm, 'TRANSACTION DETAILS')
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.line(MARGIN + 4 * mm, ty - 7.5 * mm, MARGIN + 48 * mm, ty - 7.5 * mm)

    tx_fields = [
        ('Withdrawal Reference',    withdrawal.reference),
        ('Withdrawal Method',        withdrawal.get_method_display()),
        ('Transaction Date',         withdrawal.created_at.strftime('%d %B %Y, %H:%M SAST')),
        ('Gross Withdrawal Amount',  f'R {withdrawal.amount:,.2f}'),
        ('Platform Fee',             f'R {withdrawal.fee:,.2f}'),
        ('Tax Withheld (20% WHT)',   f'R {tax_withheld:,.2f}'),
        ('Net Amount Payable',       f'R {net_amt:,.2f}'),
    ]
    row_y = ty - 14 * mm
    for label, value in tx_fields:
        c.setFont('Helvetica', 7)
        c.setFillColor(GRAY_TEXT)
        c.drawString(MARGIN + 4 * mm, row_y, label)
        is_total = 'Net' in label or 'Gross' in label
        c.setFont('Helvetica-Bold' if is_total else 'Helvetica-Bold', 8 if is_total else 8)
        c.setFillColor(GREEN if 'Net' in label else NAVY)
        c.drawRightString(W - MARGIN - 4 * mm, row_y, value)
        c.setStrokeColor(GRAY_BORDER)
        c.setLineWidth(0.3)
        c.line(MARGIN + 4 * mm, row_y - 1.5 * mm, W - MARGIN - 4 * mm, row_y - 1.5 * mm)
        row_y -= 6.5 * mm

    # ── NET AMOUNT HIGHLIGHT BOX ──────────────────────────────────
    ny = ty - 56 * mm
    _draw_rounded_rect(c, MARGIN, ny - 18 * mm, W - 2 * MARGIN, 18 * mm, 2 * mm,
                       fill_color=NAVY_DARK, stroke_color=GOLD)
    c.setFillColor(GOLD_LIGHT)
    c.setFont('Helvetica', 9)
    c.drawString(MARGIN + 6 * mm, ny - 7 * mm, 'Net Amount After Tax & Fees')
    c.setFont('Helvetica-Bold', 18)
    c.setFillColor(GOLD)
    c.drawRightString(W - MARGIN - 6 * mm, ny - 9 * mm, f'ZAR {net_amt:,.2f}')

    # ── SECTION: TAX AUTHORITY DETAILS ───────────────────────────
    ry = ny - 25 * mm
    _draw_rounded_rect(c, MARGIN, ry - 36 * mm, W - 2 * MARGIN, 36 * mm, 2 * mm,
                       fill_color=white, stroke_color=GRAY_BORDER)

    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(MARGIN + 4 * mm, ry - 6 * mm, 'TAX AUTHORITY & DECLARATION')
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.line(MARGIN + 4 * mm, ry - 7.5 * mm, MARGIN + 56 * mm, ry - 7.5 * mm)

    auth_fields = [
        ('Withholding Agent',    'InvestZA (Pty) Ltd'),
        ('Tax Reference',        withdrawal.tax_code),
        ('Tax Type',             'Dividends / Investment Withholding Tax (WHT)'),
        ('Applicable Rate',      '20% — as per South African Income Tax Act, Section 64D'),
        ('SARS Regulation',      'Income Tax Act No. 58 of 1962, as amended'),
    ]
    row_y = ry - 14 * mm
    for label, value in auth_fields:
        c.setFont('Helvetica', 7)
        c.setFillColor(GRAY_TEXT)
        c.drawString(MARGIN + 4 * mm, row_y, label)
        c.setFont('Helvetica-Bold', 7.5)
        c.setFillColor(NAVY)
        c.drawString(MARGIN + 62 * mm, row_y, value)
        row_y -= 6 * mm

    # ── DECLARATION TEXT ──────────────────────────────────────────
    dy = ry - 44 * mm
    c.setFont('Helvetica', 7)
    c.setFillColor(GRAY_TEXT)
    declaration = (
        "This certificate confirms that InvestZA (Pty) Ltd has withheld the applicable South African "
        "withholding tax on the investment returns paid to the above-named taxpayer, in accordance with "
        "the provisions of the Income Tax Act No. 58 of 1962 and the Tax Administration Act No. 28 of 2011. "
        "This document should be retained for SARS tax submission purposes."
    )
    # Simple word wrap
    words = declaration.split()
    line_width = W - 2 * MARGIN
    line, line_y = '', dy
    for word in words:
        test = (line + ' ' + word).strip()
        if c.stringWidth(test, 'Helvetica', 7) < line_width - 4 * mm:
            line = test
        else:
            c.drawString(MARGIN + 2 * mm, line_y, line)
            line_y -= 4.5 * mm
            line = word
    if line:
        c.drawString(MARGIN + 2 * mm, line_y, line)

    # ── SIGNATURE LINE ────────────────────────────────────────────
    sig_y = dy - 22 * mm
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.8)
    c.line(MARGIN, sig_y, MARGIN + 70 * mm, sig_y)
    c.line(W - MARGIN - 70 * mm, sig_y, W - MARGIN, sig_y)
    c.setFont('Helvetica', 7)
    c.setFillColor(GRAY_TEXT)
    c.drawString(MARGIN, sig_y - 4 * mm, 'Authorised Signatory — InvestZA (Pty) Ltd')
    c.drawRightString(W - MARGIN, sig_y - 4 * mm, f'Date: {now.strftime("%d %B %Y")}')

    # ── FOOTER ────────────────────────────────────────────────────
    c.setFillColor(NAVY_DARK)
    c.rect(0, 0, W, 18 * mm, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, 18 * mm, W, 0.8 * mm, fill=1, stroke=0)

    c.setFont('Helvetica', 6.5)
    c.setFillColor(HexColor('#7aa0d4'))
    footer_text = (
        f'InvestZA (Pty) Ltd  ·  Johannesburg, Gauteng, South Africa  ·  '
        f'support@investza.co.za  ·  This document was generated electronically on '
        f'{now.strftime("%d %B %Y at %H:%M SAST")} and is valid without a wet signature.'
    )
    c.drawCentredString(W / 2, 10 * mm, footer_text)
    c.setFillColor(GOLD_LIGHT)
    c.setFont('Helvetica-Bold', 6.5)
    c.drawCentredString(W / 2, 5 * mm, f'Certificate No: {cert_no}  ·  InvestZA © {now.year}  ·  All rights reserved')

    # ── WATERMARK (diagonal, very faint) ─────────────────────────
    c.saveState()
    c.setFillColor(HexColor('#0a1f44'))
    c.setFont('Helvetica-Bold', 60)
    c.setFillAlpha(0.04)
    c.translate(W / 2, H / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, 'INVESTZA CERTIFIED')
    c.restoreState()

    c.save()
    buffer.seek(0)
    return buffer.read()
