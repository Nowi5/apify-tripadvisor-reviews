import json
import csv
import os
import glob
import datetime

def jsons_to_csv(folder_path, output_csv_path):
    # Check if folder exists
    if not os.path.exists(folder_path):
        print(f"Folder does not exist: {folder_path}")
        return

    # List to hold all json data
    all_data = []

    try:
        # Find all json files in the folder
        for file_name in glob.glob(os.path.join(folder_path, '*.json')):
            with open(file_name, 'r', encoding='utf-8') as file:  # Specify encoding here
                data = json.load(file)
                all_data.append(data)

        # Check if data is found
        if not all_data:
            print("No JSON data found in the folder.")
            return

        # Write data to csv
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)

            # Writing header
            writer.writerow(all_data[0].keys())

            # Writing data rows
            for data in all_data:
                writer.writerow(data.values())

        print(f"CSV file created successfully: {output_csv_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

# Current date and time
current_datetime = datetime.datetime.now()
formatted_datetime = current_datetime.strftime("%Y_%m_%d_%H_%M_%S")

folder_path = 'storage/datasets/default'  # Replace with your folder path
output_csv_filename = 'output'  # Replace with your desired output CSV file base name
output_csv_filename_wt = f'{output_csv_filename}_{formatted_datetime}.csv'

# Call the function
jsons_to_csv(folder_path, output_csv_filename_wt)
