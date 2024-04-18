import streamlit as st
from dotenv import load_dotenv
from PyPDF2 import PdfReader
import fitz
import re
from openai import OpenAI
import os
from docx import Document
from fpdf import FPDF


# def get_pdf_text(pdf_docs):
#     text = ""
#     for pdf in pdf_docs:
#         pdf_reader = PdfReader(pdf)
#         for page in pdf_reader.pages:
#             text += page.extract_text()
#     return text

# def get_pdf_text(pdf_docs):
#     text = ""
#     seen = set()  # Set to track seen lines
#     for pdf in pdf_docs:
#         pdf_reader = PdfReader(pdf)
#         for page in pdf_reader.pages:
#             page_text = page.extract_text() or ""
#             for line in page_text.splitlines():
#                 if line not in seen:
#                     seen.add(line)
#                     text += line + "\n"
#     return text

def get_pdf_text(pdf_docs):
    text = ""
    seen = set()
    for pdf in pdf_docs:
        doc = fitz.open(stream=pdf.read(), filetype="pdf")
        for page in doc:
            page_text = page.get_text("text")
            for line in page_text.splitlines():
                if line not in seen:
                    seen.add(line)
                    text += line + "\n"
    doc.close()
    return text


def remove_references_from_text(text):
    """Removes references section from text."""
    keywords = ["References", "REFERENCES", "Bibliography", "BIBLIOGRAPHY"]
    for keyword in keywords:
        ref_index = text.find(keyword)
        if ref_index != -1:
            return text[:ref_index]
    # If no references section is found, return the original text
    return text


def remove_references_and_page_numbers(text):
    """
    Removes reference markings and page number information from the text.
    - Reference markings are typically in the format of [number] or [number,number,...].
    - Page number information is typically in the format of "X of Y".
    """
    # Regular expression to match reference markings like [1], [1,2], etc.
    pattern_references = r"\[\d+(,\d+)*\]"
    # Regular expression to match page numbers like "2 of 13"
    pattern_page_numbers = r"\d+ of \d+"
    # First, remove reference markings
    text = re.sub(pattern_references, "", text)
    # Then, remove page number information
    cleaned_text = re.sub(pattern_page_numbers, "", text)

    return cleaned_text


def split_into_chunks(text, chunk_size=1000):
    """
    Splits the text into chunks with each chunk containing complete sentences.
    The size of chunks is approximately the specified chunk_size.
    """
    chunks = []
    start = 0

    while start < len(text):
        # Find the nearest sentence end within chunk_size to chunk_size+100 characters
        # This gives some leeway to find a sentence ending and avoid very small chunks
        end = min(start + chunk_size, len(text))
        nearest_end = text.rfind('.', start, end + 100) + 1  # +1 to include the period in the chunk
        if nearest_end > 0 and nearest_end > start:
            # Found a period, try to refine to include any trailing whitespace or quotation marks
            while nearest_end < len(text) and text[nearest_end] in " \n\"'’”":
                nearest_end += 1
            chunks.append(text[start:nearest_end])
            start = nearest_end
        else:
            print("Incomp")
            chunks.append(text[start:start+chunk_size])
            start += chunk_size

    print(f"Number of chunks: {len(chunks)}")
    return chunks




def summarize_with_chatgpt(text_chunk):
    client = OpenAI()
    response = client.chat.completions.create(
    messages=[
        {
            "role": "user",
            "content": f"""
            Using only the information provided in the following text, please generate a concise summary that captures the key points, findings, and conclusions. Do not add any external information or assumptions.

            {text_chunk}

            The summary should strictly reflect the insights, methodologies, results, and conclusions presented in the text. Limit the length of the summary to 200 characters.

            """,
        }
    ],
    model="gpt-3.5-turbo",
    temperature= 0.5,
    )
    summary = response.choices[0].message.content
    return summary


def summarize_sections_with_chatgpt(text_chunk):
    client = OpenAI()
    response = client.chat.completions.create(
    messages=[
        {
            "role": "user",
            "content": f"""
            This is a summary of a clinical report titled: Unique features of dyslipidemia in women across a lifetime and a tailored approach to management

            {text_chunk}

            Go through the entire summary and divide the given content into these three sections: Objective, method and result. Do not add any new information and only use the content provided in this summary. The length of your response should be at least 1000 words. Make each of the sections with bullet points and not full paragraphs.

            """,

        }
    ],
    model="gpt-3.5-turbo",
    temperature= 0.7,
    )
    summary = response.choices[0].message.content
    return summary


def create_word_document(text, filename="Summary.docx"):
    doc = Document()
    doc.add_paragraph(text)
    doc.save(filename)
    return filename


def create_pdf_document(text, filename="Summary.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size = 12)
    pdf.multi_cell(0, 10, text)
    pdf.output(filename)
    return filename

def main():
    # Load environment variables from a .env file
    load_dotenv()

    # Set the configuration for the Streamlit page
    st.set_page_config(page_title="Clinical Summary", page_icon=":books")

    # Display the application header
    st.header("Clinical Summary :books:")

    with st.sidebar:
        st.subheader("Your documents")
        # Allow users to upload PDF documents
        pdf_docs = st.file_uploader("Upload your PDFs here and click on 'Process'", accept_multiple_files=True)
        process_button = st.button("Process")
    
    # Initialize session state for the text area if it doesn't exist
    if 'processed_text' not in st.session_state:
        st.session_state.processed_text = ""
    
    if 'summary_text' not in st.session_state:
        st.session_state.summary_text = ""

    # Initialize a variable to hold the combined text of all uploaded PDFs
    if process_button and pdf_docs:
        with st.spinner("Processing"):
            initialEdit = ""
            
            # Extract text from the uploaded PDF
            pdf_text = get_pdf_text(pdf_docs)
            raw_text = remove_references_from_text(pdf_text)
            raw_text_removeInLineRef = remove_references_and_page_numbers(raw_text)
            initialEdit = raw_text_removeInLineRef  # Separate texts of different PDFs

        st.session_state.processed_text = initialEdit
        st.session_state.summary_text = "" 

    # Display the text area with the text stored in session state
    if st.session_state.processed_text:
        edited_text = st.text_area("Edit the processed text:", st.session_state.processed_text, height=500, key='text_area')
        st.session_state.processed_text = edited_text  # Update session state with edited text

    # Add a button to generate summary
    if st.button('Generate Summary'):
        if st.session_state.processed_text:
            with st.spinner('Generating Summary...'):
                chunk_list = []
                chunks = split_into_chunks(st.session_state.processed_text)
                for chunk in chunks:
                    chunk_list.append(summarize_with_chatgpt(chunk))
                full_summary = " ".join(chunk_list)
                st.session_state.summary_text = summarize_sections_with_chatgpt(full_summary)

    # Display the summary text area with the summary stored in session state
    if st.session_state.summary_text:
        st.session_state.summary_text = st.text_area("Summary:", value=st.session_state.summary_text, height=300, key='summary_area')

        # Buttons for downloading the summary as Word or PDF
        word_file = create_word_document(st.session_state.summary_text)
        pdf_file = create_pdf_document(st.session_state.summary_text)
        
        
        st.download_button(label="Download as Word", data=open(word_file, "rb"), file_name=word_file, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        st.download_button(label="Download as PDF", data=open(pdf_file, "rb"), file_name=pdf_file, mime="application/pdf")




# Execute the main function when the script is run directly
if __name__ == '__main__':
    main()