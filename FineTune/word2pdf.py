from docx import Document
from fpdf import FPDF


def convert_docx_to_pdf(docx_file, pdf_path):
    # Load the Word document
    doc = Document(docx_file)

    # Initialize FPDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Add a page
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Iterate through each paragraph in the docx
    for para in doc.paragraphs:
        pdf.multi_cell(0, 10, para.text)

    # Save the PDF
    pdf.output(pdf_path)

if __name__ == '__main__':
    # Example usage
    convert_docx_to_pdf("example.docx", "output.pdf")