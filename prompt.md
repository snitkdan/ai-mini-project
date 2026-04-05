I want you to write a simple Python app that has a few components. It is essentially a gRPC server that kicks off a Temporal Workflow that forwards user prompts to the Gemini API (LLM) and echoes the response to a SQLite database. 

Component1: A Database module that uses SQLite. The table should be called `transactions`, and the schema should be `id (integer primary key autoincrement), prompt (text), timestamp, response`. Make sure that the timestamp is a proper type based on best practices for SQLite timestamps. There should be a script to initialize the DB file that is one-off. There should also be a file that includes a client to this DB for inserting a row, querying by id, and listing all rows. Place these files in a folder called `storage`. 

Component2: A Temporal workflow with 2 activities:
 -> (1) that POSTs to `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent` using an `API_KEY = os.getenv("GEMINI_API_KEY")` (loaded in using python `dotenv.load_dotenv`), forwarding a prompt as an argument and returning the result. 
 -> (2) That saves the call to the Database in Component 1. 
Add the worker, workflow, and activity files in a `workflow` directory. Use `localhost:7233` as the Temporal server address and `"gemini-echo"` as the task queue name. 

Component3: A gRPC server that kicks off Component 2 workflow, taking in a request `prompt` and printing the `output`. The server is called `GeminiEchoServer`, and you should name the Request / Response similarly. Add the grpc_server in a folder called `server`. Ensure that shutdown like Ctrl-C are handled gracefully. You can use insecure_ports. The gRPC server should execute the workflow synchronously (await the result before responding to the caller).

Component4: A simple gRPC client script that accepts 1 CLI argument for `prompt` and forwards to the gRPC server. It then queries the Database for the most recent record and outputs the row. Make sure that output is human-legible and clean. You can use insecure_channel. Put this file in a folder called `client`. The client imports gRPC stubs from `proto/generated`.

Principles for all components:
(0) Ensure all Python scripts that are runnable have `#!/usr/bin/env python3`.
(1) Use Python type-annotations everywhere, nothing should be untyped. 
(2) Add README files to all directories to show usage of scripts. 
(3) Assume all dependencies are pip/brew installed, so don't spend time setting any of this up. Assume you have a Virtual Env that will run things without installation. 
(4) Place the `.proto` file in `proto/` and compile generated stubs into `proto/generated/`. Fix the well-known broken import bug in generated gRPC stubs (the generated `*_pb2_grpc.py` uses `import gemini_echo_pb2` instead of `from . import gemini_echo_pb2`) by patching `proto/generated/__init__.py` to register the `*_pb2` module under its bare name in `sys.modules` before the broken import runs — do not modify the generated files directly.
(5) Don't output generated protos; just tell me what to run and where to place the files. 
(6) No additional error handling is required beyond what naturally surfaces as exceptions.