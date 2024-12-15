# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas",
#   "matplotlib",
#   "seaborn",
#   "openai",
#   "scikit-learn",
#   "pillow",
#   "ipykernel",
#   "requests",  # Add requests as an inline dependency
# ]
# ///

import os
import sys
import subprocess
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.impute import SimpleImputer
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import openai
import base64
try:
    import requests  # Try importing requests
except ImportError:
    # If requests is not found, install it inline
    print("requests module not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests  # Try importing again after installation
from PIL import Image

# Set matplotlib backend to avoid GUI-related errors
plt.switch_backend('Agg')

# Retrieve the AIPROXY_TOKEN from the environment variable
try:
    AIPROXY_TOKEN = os.environ["AIPROXY_TOKEN"]
except KeyError:
    print("Error: AIPROXY_TOKEN environment variable is not set.")
    sys.exit(1)

openai.api_key = AIPROXY_TOKEN
openai.api_base = "https://aiproxy.sanand.workers.dev/openai/v1"

# Maximum section and total prompt length (in characters)
MAX_SECTION_LENGTH = 1000  # Max length for each section
MAX_TOTAL_LENGTH = 4000  # Max length for the entire prompt

def truncate_text(text, max_length):
    """Truncate text to fit within the maximum length."""
    if len(text) > max_length:
        return text[:max_length] + "..."  # Add ellipsis to indicate truncation
    return text

def load_data(file_path):
    """Loads the dataset and handles encoding issues."""
    print("Loading dataset...")
    try:
        df = pd.read_csv(file_path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding="ISO-8859-1")
    print("Dataset loaded successfully!")
    return df

def preprocess_data(df):
    """Preprocesses the data by handling missing values."""
    print("Preprocessing data...")
    imputer = SimpleImputer(strategy="mean")
    df_imputed = pd.DataFrame(imputer.fit_transform(df.select_dtypes(include=["float64", "int64"])),
                              columns=df.select_dtypes(include=["float64", "int64"]).columns)
    df.update(df_imputed)
    print("Preprocessing complete.")
    return df

def plot_correlation_matrix(df, output_file="correlation_matrix.png"):
    """Plots and saves the correlation matrix."""
    print("Plotting correlation matrix...")
    numeric_df = df.select_dtypes(include=["float64", "int64"])
    if numeric_df.empty:
        print("No numeric data available for correlation matrix.")
        return None
    corr = numeric_df.corr()
    plt.figure(figsize=(10, 8))
    sns.heatmap(corr, annot=True, cmap="coolwarm", fmt=".2f", square=True)
    plt.title("Correlation Matrix")
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()
    print(f"Correlation matrix saved as {output_file}.")
    return corr.to_dict()

def perform_pca(df, output_file="pca_variance.png"):
    """Performs PCA and saves explained variance plot."""
    print("Performing PCA...")
    numeric_df = df.select_dtypes(include=["float64", "int64"])
    if numeric_df.empty:
        print("No numeric data available for PCA.")
        return None, None

    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(numeric_df)

    pca = PCA()
    pca.fit(scaled_data)
    explained_variance = pca.explained_variance_ratio_
    pca_components = pca.components_

    # Save the explained variance plot
    plt.figure(figsize=(10, 6))
    plt.plot(range(1, len(explained_variance) + 1), explained_variance, marker='o', linestyle='--', color='b')
    plt.title("PCA Explained Variance")
    plt.xlabel("Principal Component")
    plt.ylabel("Variance Explained")
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()
    print(f"PCA explained variance plot saved as {output_file}.")

    return explained_variance.tolist(), pca_components

def perform_analysis(df):
    """Performs various analysis and generates plots."""
    print("Performing analysis...")
    results = {}

    # Outlier Detection
    results["outliers"] = df.describe().to_dict()

    # Correlation Analysis
    results["correlation"] = plot_correlation_matrix(df)

    # PCA Analysis
    explained_variance, pca_components = perform_pca(df)

    results["pca_explained_variance"] = explained_variance
    results["pca_components"] = pca_components.tolist()  # Converting to list for easier readability

    # Value Counts Analysis (do not plot, but include in the prompt)
    categorical_cols = df.select_dtypes(include=["object"]).columns
    value_counts = {}
    for col in categorical_cols:
        value_counts[col] = df[col].value_counts().to_dict()

    print("Analysis complete.")
    return results, value_counts

def generate_prompt(data_analysis, value_counts):
    """Generates the prompt for the LLM."""
    print("Generating prompt for LLM...")

    dataset_summary = truncate_text(str(data_analysis.get("outliers", "Dataset summary not available.")), MAX_SECTION_LENGTH)
    correlation_analysis = truncate_text(str(data_analysis.get("correlation", "Correlation analysis not available.")), MAX_SECTION_LENGTH)
    value_counts_analysis = truncate_text(str(value_counts), MAX_SECTION_LENGTH)  # Directly pass the value counts
    clustering_insights = truncate_text(str(data_analysis.get("clusters", "No clustering performed.")), MAX_SECTION_LENGTH)

    # Create the prompt with truncated sections
    prompt = f"""
    Analyze the following data and provide insights:

    Dataset Summary:
    {dataset_summary}

    Correlation Analysis:
    {correlation_analysis}

    Value Counts Analysis:
    {value_counts_analysis}

    Clustering Insights:
    {clustering_insights}

    Implications:
    Please explain the findings and their implications.
    """

    # Ensure total length does not exceed the limit
    prompt = truncate_text(prompt, MAX_TOTAL_LENGTH)

    print("Prompt generation complete.")
    return prompt

def query_llm(prompt):
    """Queries the LLM for narrative generation using AI Proxy."""
    print("Querying the LLM...")
    API_URL = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AIPROXY_TOKEN}"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a data analyst assistant."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()  # Raises an HTTPError if the status code is 4xx/5xx
        data = response.json()
        narrative = data["choices"][0]["message"]["content"]
        print("Narrative generated successfully.")
        return narrative
    except requests.exceptions.RequestException as e:
        print(f"Error with LLM request: {e}")
        return "LLM request failed. Narrative generation was unsuccessful."

def save_readme(narrative, image_files):
    """Saves the narrative to README.md along with images, limiting to 3 images."""
    print("Saving README.md...")
    readme_content = f"{narrative}\n\n### Visualizations:\n\n"
    image_count = 0

    # Only save the first two images to README.md (max 2 images)
    for image in image_files:
        if os.path.exists(image) and image_count < 3:
            encoded_image = base64.b64encode(open(image, "rb").read()).decode("utf-8")
            readme_content += f"![{image.split('.')[0]}](data:image/png;base64,{encoded_image})\n\n"
            image_count += 1

    with open("README.md", "w") as f:
        f.write(readme_content)
    print("README.md saved successfully.")

def main(file_path):
    """Main function to orchestrate analysis."""
    df = load_data(file_path)
    df = preprocess_data(df)
    data_analysis, value_counts = perform_analysis(df)

    # Define image files
    image_files = [
        "correlation_matrix.png",
        "pca_variance.png"
    ]

    # Generate the prompt with all images and value counts
    prompt = generate_prompt(data_analysis, value_counts)
    narrative = query_llm(prompt)

    # Save README with up to 3 images
    save_readme(narrative, image_files)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please provide a CSV file as an argument.")
        sys.exit(1)
    main(sys.argv[1])
