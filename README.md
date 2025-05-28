First, configure python main.py in the terminal
Second, open another terminal window and open the port of the server you're sending the files to 
Command: uvicorn server:app --host 0.0.0.0 --port 8000

Finally, set the port in ngrok to ngrok http 8000 to enable encrypted transfers.
Please keep this in mind when using it.
