"""
PDF generation service for invoices and proposals.

WHAT: Generates professional PDF documents using ReportLab.

WHY: PDF generation is critical for:
1. Professional invoice documents (PDF-002)
2. Proposal documents for client review (PDF-003)
3. Record keeping and compliance
4. Print-ready documents

HOW: Uses ReportLab for pure Python PDF generation:
- No external dependencies (no wkhtmltopdf, Chrome, etc.)
- Template-based design for consistent branding
- Supports tables, headers, footers
- Returns bytes for direct download or email attachment

Design decisions:
- On-demand generation: PDFs generated when requested, not stored
- Template approach: Reusable layouts for consistency
- Company branding: Configurable header/footer
- Currency formatting: Proper decimal handling
"""

import io
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

from app.models.invoice import Invoice, InvoiceStatus
from app.models.proposal import Proposal

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================


@dataclass
class CompanyInfo:
    """
    Company branding information for PDFs.

    WHY: Centralizes company info for consistent branding
    across all generated documents.
    """

    name: str = "Automation Platform"
    address: str = "123 Business St, Suite 100"
    city_state_zip: str = "San Francisco, CA 94105"
    phone: str = "(555) 123-4567"
    email: str = "billing@example.com"
    website: str = "www.example.com"
    logo_path: Optional[str] = None


# Default company info - can be overridden per organization
DEFAULT_COMPANY_INFO = CompanyInfo()


# ============================================================================
# PDF Styles
# ============================================================================


def get_styles():
    """
    Get PDF document styles.

    WHY: Centralized styles ensure consistent formatting.

    Returns:
        Dictionary of ParagraphStyle objects
    """
    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(
        name='DocumentTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=20,
        textColor=colors.HexColor('#1a365d'),
    ))

    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10,
        textColor=colors.HexColor('#2d3748'),
    ))

    styles.add(ParagraphStyle(
        name='BodyText',
        parent=styles['Normal'],
        fontSize=10,
        spaceBefore=5,
        spaceAfter=5,
    ))

    styles.add(ParagraphStyle(
        name='SmallText',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#718096'),
    ))

    styles.add(ParagraphStyle(
        name='RightAlign',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT,
    ))

    styles.add(ParagraphStyle(
        name='AmountText',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT,
        fontName='Helvetica-Bold',
    ))

    styles.add(ParagraphStyle(
        name='TotalText',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_RIGHT,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a365d'),
    ))

    return styles


# ============================================================================
# Helper Functions
# ============================================================================


def format_currency(amount: Any) -> str:
    """
    Format amount as USD currency.

    WHAT: Converts decimal/float to formatted currency string.

    WHY: Consistent currency display across all documents.

    Args:
        amount: Amount to format (Decimal, float, int, or None)

    Returns:
        Formatted currency string (e.g., "$1,234.56")
    """
    if amount is None:
        return "$0.00"

    try:
        value = float(amount)
        return f"${value:,.2f}"
    except (ValueError, TypeError):
        return "$0.00"


def format_date(d: Any) -> str:
    """
    Format date for display.

    WHAT: Converts date to readable format.

    WHY: Consistent date display across documents.

    Args:
        d: Date to format (date, datetime, or None)

    Returns:
        Formatted date string (e.g., "January 15, 2024")
    """
    if d is None:
        return ""

    if isinstance(d, datetime):
        d = d.date()

    if isinstance(d, date):
        return d.strftime("%B %d, %Y")

    return str(d)


# ============================================================================
# PDF Service
# ============================================================================


class PDFService:
    """
    Service for generating PDF documents.

    WHAT: Creates professional PDF documents for invoices and proposals.

    WHY: Provides:
    - Professional document generation
    - Consistent branding
    - Print-ready output
    - Email-attachable files

    HOW: Uses ReportLab's platypus for document layout.
    """

    def __init__(self, company_info: Optional[CompanyInfo] = None):
        """
        Initialize PDF service.

        Args:
            company_info: Company branding info (defaults to DEFAULT_COMPANY_INFO)
        """
        self.company = company_info or DEFAULT_COMPANY_INFO
        self.styles = get_styles()

    def _build_header(self, doc_type: str, doc_number: str) -> List:
        """
        Build document header with company info.

        WHY: Consistent header across all document types.

        Args:
            doc_type: "INVOICE" or "PROPOSAL"
            doc_number: Document number for display

        Returns:
            List of flowable elements for header
        """
        elements = []

        # Company name as title
        elements.append(Paragraph(self.company.name, self.styles['DocumentTitle']))

        # Company contact info
        contact_text = f"""
        {self.company.address}<br/>
        {self.company.city_state_zip}<br/>
        {self.company.phone} | {self.company.email}
        """
        elements.append(Paragraph(contact_text, self.styles['SmallText']))

        elements.append(Spacer(1, 20))

        # Document type and number
        header_data = [
            [doc_type, doc_number],
        ]
        header_table = Table(header_data, colWidths=[3 * inch, 4 * inch])
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 18),
            ('TEXTCOLOR', (0, 0), (0, 0), colors.HexColor('#2563eb')),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica'),
            ('FONTSIZE', (1, 0), (1, 0), 12),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(header_table)

        elements.append(Spacer(1, 15))

        return elements

    def _build_client_info(
        self,
        client_name: str,
        client_address: Optional[str] = None,
        dates: List[tuple] = None,
    ) -> List:
        """
        Build client information section.

        WHY: Shows who the document is for and key dates.

        Args:
            client_name: Client/organization name
            client_address: Optional client address
            dates: List of (label, value) date tuples

        Returns:
            List of flowable elements
        """
        elements = []

        # Create two-column layout: client info on left, dates on right
        left_content = [
            Paragraph("<b>Bill To:</b>", self.styles['BodyText']),
            Paragraph(client_name, self.styles['BodyText']),
        ]
        if client_address:
            left_content.append(Paragraph(client_address, self.styles['BodyText']))

        right_content = []
        if dates:
            for label, value in dates:
                right_content.append(
                    Paragraph(f"<b>{label}:</b> {value}", self.styles['RightAlign'])
                )

        # Build as table for alignment
        info_data = [[
            left_content,
            right_content,
        ]]

        info_table = Table(info_data, colWidths=[3.5 * inch, 3.5 * inch])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))

        elements.append(info_table)
        elements.append(Spacer(1, 20))

        return elements

    def _build_line_items_table(
        self,
        line_items: List[dict],
        show_unit_price: bool = True,
    ) -> Table:
        """
        Build line items table.

        WHY: Core content of invoices and proposals.

        Args:
            line_items: List of line item dictionaries
            show_unit_price: Whether to show quantity and unit price columns

        Returns:
            Table element with styled line items
        """
        if show_unit_price:
            headers = ['Description', 'Qty', 'Unit Price', 'Amount']
            col_widths = [3.5 * inch, 0.75 * inch, 1.25 * inch, 1.5 * inch]
        else:
            headers = ['Description', 'Amount']
            col_widths = [5.5 * inch, 1.5 * inch]

        data = [headers]

        for item in line_items:
            if show_unit_price:
                row = [
                    item.get('description', ''),
                    str(item.get('quantity', 1)),
                    format_currency(item.get('unit_price', 0)),
                    format_currency(item.get('amount', 0)),
                ]
            else:
                row = [
                    item.get('description', ''),
                    format_currency(item.get('amount', 0)),
                ]
            data.append(row)

        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f7fafc')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),

            # Data rows
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 8),

            # Alignment
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),

            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
        ]))

        return table

    def _build_totals_table(
        self,
        subtotal: Any,
        discount_amount: Any = None,
        tax_amount: Any = None,
        total: Any = None,
        amount_paid: Any = None,
    ) -> Table:
        """
        Build totals summary table.

        WHY: Shows financial summary on invoice/proposal.

        Args:
            subtotal: Subtotal before adjustments
            discount_amount: Discount applied
            tax_amount: Tax amount
            total: Grand total
            amount_paid: Amount already paid (for invoices)

        Returns:
            Table element with totals
        """
        data = []

        data.append(['Subtotal', format_currency(subtotal)])

        if discount_amount and float(discount_amount) > 0:
            data.append(['Discount', f"-{format_currency(discount_amount)}"])

        if tax_amount and float(tax_amount) > 0:
            data.append(['Tax', format_currency(tax_amount)])

        data.append(['', ''])  # Spacer row

        data.append(['Total', format_currency(total)])

        if amount_paid is not None and float(amount_paid) > 0:
            data.append(['Amount Paid', f"-{format_currency(amount_paid)}"])
            balance = float(total or 0) - float(amount_paid or 0)
            data.append(['Balance Due', format_currency(balance)])

        table = Table(data, colWidths=[1.5 * inch, 1.5 * inch])

        # Style setup
        style_commands = [
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]

        # Find Total row and style it differently
        for i, row in enumerate(data):
            if row[0] in ['Total', 'Balance Due']:
                style_commands.extend([
                    ('FONTNAME', (0, i), (1, i), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, i), (1, i), 12),
                    ('TEXTCOLOR', (0, i), (1, i), colors.HexColor('#1a365d')),
                    ('LINEABOVE', (0, i), (1, i), 1, colors.HexColor('#2d3748')),
                ])

        table.setStyle(TableStyle(style_commands))
        return table

    def _build_footer(self, notes: Optional[str] = None, terms: Optional[str] = None) -> List:
        """
        Build document footer with notes and terms.

        WHY: Important legal and payment information.

        Args:
            notes: Additional notes
            terms: Terms and conditions

        Returns:
            List of flowable elements
        """
        elements = []

        if notes:
            elements.append(Paragraph("<b>Notes:</b>", self.styles['SectionHeader']))
            elements.append(Paragraph(notes, self.styles['BodyText']))
            elements.append(Spacer(1, 10))

        if terms:
            elements.append(Paragraph("<b>Terms & Conditions:</b>", self.styles['SectionHeader']))
            elements.append(Paragraph(terms, self.styles['BodyText']))

        return elements

    # ========================================================================
    # Invoice PDF Generation
    # ========================================================================

    def generate_invoice_pdf(
        self,
        invoice: Invoice,
        client_name: str,
        client_address: Optional[str] = None,
        line_items: Optional[List[dict]] = None,
    ) -> bytes:
        """
        Generate PDF for an invoice.

        WHAT: Creates a professional invoice PDF.

        WHY: Invoices need to be:
        - Professional looking
        - Print-ready
        - Email attachable
        - Legally compliant

        Args:
            invoice: Invoice model instance
            client_name: Client/organization name
            client_address: Optional client address
            line_items: Optional line items (if not stored on invoice)

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        elements = []

        # Header
        elements.extend(self._build_header("INVOICE", invoice.invoice_number))

        # Status badge (if not draft)
        if invoice.status != InvoiceStatus.DRAFT:
            status_text = invoice.status.value.upper()
            status_color = {
                'sent': '#3182ce',
                'paid': '#38a169',
                'overdue': '#e53e3e',
                'cancelled': '#718096',
                'refunded': '#805ad5',
                'partially_paid': '#dd6b20',
            }.get(invoice.status.value, '#718096')

            elements.append(Paragraph(
                f"<font color='{status_color}'><b>STATUS: {status_text}</b></font>",
                self.styles['BodyText']
            ))
            elements.append(Spacer(1, 10))

        # Client info and dates
        dates = [
            ('Invoice Date', format_date(invoice.issue_date)),
            ('Due Date', format_date(invoice.due_date) if invoice.due_date else 'Upon Receipt'),
        ]
        if invoice.paid_at:
            dates.append(('Paid Date', format_date(invoice.paid_at)))

        elements.extend(self._build_client_info(client_name, client_address, dates))

        # Line items (generate from totals if not provided)
        if not line_items:
            line_items = [
                {
                    'description': f'Invoice {invoice.invoice_number}',
                    'quantity': 1,
                    'unit_price': float(invoice.subtotal),
                    'amount': float(invoice.subtotal),
                }
            ]

        elements.append(self._build_line_items_table(line_items))
        elements.append(Spacer(1, 20))

        # Totals (right-aligned)
        totals_data = [[
            '',
            self._build_totals_table(
                subtotal=invoice.subtotal,
                discount_amount=invoice.discount_amount,
                tax_amount=invoice.tax_amount,
                total=invoice.total,
                amount_paid=invoice.amount_paid,
            )
        ]]
        totals_layout = Table(totals_data, colWidths=[4 * inch, 3 * inch])
        totals_layout.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(totals_layout)
        elements.append(Spacer(1, 20))

        # Notes
        if invoice.notes:
            elements.extend(self._build_footer(notes=invoice.notes))

        # Build PDF
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(f"Generated invoice PDF: {invoice.invoice_number}")
        return pdf_bytes

    # ========================================================================
    # Proposal PDF Generation
    # ========================================================================

    def generate_proposal_pdf(
        self,
        proposal: Proposal,
        client_name: str,
        client_address: Optional[str] = None,
    ) -> bytes:
        """
        Generate PDF for a proposal.

        WHAT: Creates a professional proposal PDF.

        WHY: Proposals need to be:
        - Professional and branded
        - Easy to review
        - Include all pricing details
        - Printable for signatures

        Args:
            proposal: Proposal model instance
            client_name: Client/organization name
            client_address: Optional client address

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        elements = []

        # Header
        proposal_number = f"P-{proposal.id:04d}"
        if proposal.version > 1:
            proposal_number += f" (v{proposal.version})"
        elements.extend(self._build_header("PROPOSAL", proposal_number))

        # Title
        elements.append(Paragraph(proposal.title, self.styles['SectionHeader']))
        elements.append(Spacer(1, 10))

        # Client info and dates
        dates = [
            ('Date', format_date(proposal.created_at)),
            ('Valid Until', format_date(proposal.valid_until) if proposal.valid_until else 'N/A'),
        ]
        elements.extend(self._build_client_info(client_name, client_address, dates))

        # Description
        if proposal.description:
            elements.append(Paragraph("<b>Project Description:</b>", self.styles['SectionHeader']))
            elements.append(Paragraph(proposal.description, self.styles['BodyText']))
            elements.append(Spacer(1, 15))

        # Line items
        if proposal.line_items:
            elements.append(Paragraph("<b>Pricing Details:</b>", self.styles['SectionHeader']))
            elements.append(self._build_line_items_table(proposal.line_items))
            elements.append(Spacer(1, 20))

        # Totals
        totals_data = [[
            '',
            self._build_totals_table(
                subtotal=proposal.subtotal,
                discount_amount=proposal.discount_amount,
                tax_amount=proposal.tax_amount,
                total=proposal.total,
            )
        ]]
        totals_layout = Table(totals_data, colWidths=[4 * inch, 3 * inch])
        totals_layout.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(totals_layout)
        elements.append(Spacer(1, 20))

        # Notes and terms
        elements.extend(self._build_footer(
            notes=proposal.client_notes,
            terms=proposal.terms,
        ))

        # Signature section
        elements.append(Spacer(1, 30))
        elements.append(Paragraph("<b>Acceptance:</b>", self.styles['SectionHeader']))
        elements.append(Paragraph(
            "By signing below, you accept this proposal and authorize the work to begin.",
            self.styles['BodyText']
        ))
        elements.append(Spacer(1, 20))

        # Signature lines
        sig_data = [
            ['_' * 40, '_' * 20],
            ['Signature', 'Date'],
            ['', ''],
            ['_' * 40, ''],
            ['Printed Name', ''],
        ]
        sig_table = Table(sig_data, colWidths=[3 * inch, 2 * inch])
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(sig_table)

        # Build PDF
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(f"Generated proposal PDF: {proposal_number}")
        return pdf_bytes


# ============================================================================
# Module-level convenience functions
# ============================================================================


_pdf_service: Optional[PDFService] = None


def get_pdf_service() -> PDFService:
    """
    Get or create the global PDF service instance.

    WHY: Singleton pattern ensures consistent configuration
    and resource sharing.

    Returns:
        PDFService instance
    """
    global _pdf_service

    if _pdf_service is None:
        _pdf_service = PDFService()

    return _pdf_service
