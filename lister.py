import asyncio
import aiohttp
import json
import argparse
import ssl
from itertools import islice
from urllib.parse import urlparse

# Async function to handle Gemini requests
async def gemini_request(session, text):
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
    async with session.post(url, headers=headers, json=payload) as response:
        if response.status == 200:
            return parse_gemini_response(await response.json())  # No need to await `response.json()`
        else:
            print(f"[!] Error: {response.status}")
            return None

# Parse the response from Gemini API
def parse_gemini_response(response):
    # Access the text content
    text_content = response["candidates"][0]["content"]["parts"][0]["text"].split('\n')
    gemini_domains = [x for x in text_content if x]
    return gemini_domains

# Write the subdomains or directories to an output file
def write_subs(outfile, response_text):
    with open(outfile, 'a') as out_fd:
        for line in response_text:
            out_fd.write(f"{line}\n")
    return

# Async function to generate requests in batches
async def generate_requests(domains, prompt, outfile, batch_size, disable_ssl):
    # Disable SSL verification if requested
    connector = aiohttp.TCPConnector(ssl=False) if disable_ssl else aiohttp.TCPConnector()
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for batch in batch_iterable(domains, batch_size):
            batch_text = "<".join(batch)
            tasks.append(asyncio.create_task(handle_batch(session, batch_text, prompt, outfile)))
        await asyncio.gather(*tasks)

# Handle a single batch
async def handle_batch(session, batch_text, prompt, outfile):
    gemini_response = await gemini_request(session, f"{prompt} {batch_text}")
    if gemini_response and outfile:
        write_subs(outfile, gemini_response)
    print("[!] Generated entries:")
    for r in gemini_response:
        print(r)

# Utility function to create batches
def batch_iterable(iterable, batch_size):
    iterator = iter(iterable)
    while batch := list(islice(iterator, batch_size)):
        yield batch

# Load config from file
def load_config(config_file):
    with open(config_file, 'r') as file:
        return json.load(file)

# Read domains from the input file
def read_domains(input_file):
    with open(input_file, 'r') as file:
        return [line.strip() for line in file.readlines() if line.strip()]

# Main function
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
    parser.add_argument("--disable_ssl", help="Disable SSL verification for requests.", action="store_true")  # New argument
    args = parser.parse_args()

    config = load_config(args.config_file)
    domain_mode = True
    directory_mode = False
    batch_size = 100

    if args.batch_size:
        batch_size = int(args.batch_size)
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

    # Run the async batch generation with the disable_ssl flag
    asyncio.run(generate_requests(entries, prompt, args.output, batch_size, args.disable_ssl))

if __name__ == "__main__":
    main()
