from graphviz import Digraph

dot = Digraph(comment="Persona Simulator System Architecture")

# Define the nodes
dot.node("UI", "Streamlit App")
dot.node("BL", "Backend Logic (Code)")
dot.node("GPT", "GPT-4 (Clarifai)")
dot.node("SDXL", "Stable-Diffusion-XL (Clarifai)")
dot.node("DB", "DynamoDB")
dot.node("S3", "S3 (Image Blobs)")

# Define the edges
dot.edge("UI", "BL", 'User interactions, Provide "nudge", View Plan & Rationale')
dot.edge("BL", "GPT", "Send prompts, Receive decisions, Convert plan to JSON")
dot.edge("BL", "SDXL", "Generate images")
dot.edge("BL", "DB", "Write/Read Thought records, Save content (Journal, Blog, SM Posts)")
dot.edge("BL", "S3", "Save Image blobs")

# Save the output
dot.render("persona_simulator_architecture.gv", view=True)  # This saves and opens the diagram
