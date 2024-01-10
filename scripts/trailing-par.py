import glob
import pandas as pd

for f in glob.glob('../data/references/*.csv'):
    df = pd.read_csv(f)
    # Group by the 'paragraph' column and aggregate the 'page' column as a list
    grouped = df.groupby('paragraph')['page'].agg(list)

    # Filter groups with more than one unique page
    duplicates = grouped[grouped.apply(lambda x: len(set(x)) > 1)]
    # Print the results
    for paragraph, pages in duplicates.items():
        print(f"Paragraph {paragraph} is present on pages: {', '.join(map(str, pages))}")

# -> None!