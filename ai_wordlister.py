from itertools import islice
import json
import requests
import argparse
from urllib.parse import urlparse

def extract_directories(urls):
    directories = set()
    for url in urls:
        parsed = urlparse(url)
        path = parsed.path
        if path and path != "/":
            parts = path.strip("/").split("/")
            for i in range(1, len(parts) + 1):
                directories.add("/" + "/".join(parts[:i]))
    return list(directories)

def batch_iterable(iterable, batch_size):
    iterator = iter(iterable)
    while batch := list(islice(iterator, batch_size)):
        yield batch

def load_config(config_file):
    with open(config_file, 'r') as file:
        return json.load(file)

def read_domains(input_file):
    with open(input_file, 'r') as file:
        return [line.strip() for line in file.readlines() if line.strip()]

def gemini_request(text):
    global config
    api_key = config.get("GEMINI_API_KEY")
    if api_key is None:
        print("[!] Could not detect Gemini API key")
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": text}]}]
    }
    response = requests.post(url, headers=headers, json=payload)
    if response is not None:
        return parse_gemini_response(response.json())
    else:
        return None

def parse_gemini_response(response):
    # Access the text content
    text_content = response["candidates"][0]["content"]["parts"][0]["text"].split('\n')
    gemini_domains = [x for x in text_content if x]
    return gemini_domains

def write_subs(outfile,response_text):
    with open(outfile,'a') as out_fd:
        for line in response_text:
            out_fd.write(f"{line}\n")
    return

def generate_requests(domains,prompt,outfile):
    for batch in batch_iterable(domains, 100):
        batch_text = "<".join(batch)
        gemini_response = gemini_request(f"{prompt} {batch_text}")
        if outfile is not None:
            write_subs(outfile,gemini_response)
        print("[!] Generated entries:")
        for r in gemini_response:
            print(r)


    return

def main():
    global config
    parser = argparse.ArgumentParser(description="Make API requests using domains and API keys from config file.")
    parser.add_argument("-d", "--directory_mode", help="Generate directories instead of subdomains based on a list of URLs", action="store_true")
    parser.add_argument("-s", "--domain_mode", help="Generate subdomains instead of directories. (Default= yes)", action="store_true")
    parser.add_argument("-f", "--input_file", help="File containing a list of domains.", required=True)
    parser.add_argument("-c", "--config_file", help="JSON config file with API keys.", required=True)
    parser.add_argument("-p", "--prompt", help="E.g. Subdomains separated by a <. Use this list as a seed, generate X new subdomains. Only return subdomains for DOMAIN.")
    parser.add_argument("-b", "--batch_size", help="Batched request size. Default is 100.")
    parser.add_argument("-o", "--output", help="Write subdomains to a file.")
    args = parser.parse_args()

    config = load_config(args.config_file)
    domain_mode = True
    directory_mode = False
    batch_size = 100

    if args.batch_size:
        batch_size = args.batch_size
    if args.directory_mode:
        domain_mode = False
        directory_mode = True
    if args.prompt:
        prompt = args.prompt
    elif domain_mode:
        prompt = "There are {batch_size} subdomains separated by a < character. Using this list as a seed, generate 150 new possible subdomains. Only return the subdomains. No explanations or numbering."
    else:
        prompt = "There are {batch_size} URLs separated by a < character. Using this list as a seed, generate 150 new possible directories for the site. Only return the directories. No explanations or numbering."
    entries = read_domains(args.input_file)
    generate_requests(entries,prompt,args.output)

    return

if __name__ == "__main__":
    main()

