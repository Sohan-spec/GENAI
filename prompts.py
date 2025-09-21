def build_prompt_from_tags(tags):
    tags_text = ", ".join(tags)
    prompt = f"You are an empathetic art historian and creative writer. Given the following detected elements in a painting: {tags_text}.\n\nGenerate:\n1) A vivid 180-260 word story behind this art (cultural references, symbolism, tone respectful).\n2) A short 'purpose' (1-2 sentences) explaining what the artwork communicates or is used for.\n3) A short artist biography/narrative (2-3 lines) that could plausibly describe the creator or the persona behind it.\n\nReturn the three parts separated by a line containing only '---' so they can be programmatically split."
    return prompt




def build_prompt_from_text(idea_text):
    prompt = f"You are an imaginative art guide. The user idea: \"{idea_text}\".\n\nGenerate:\n1) A unique art idea / composition (detailed, original, and not a copy of common art) in 3-6 sentences.\n2) A 150-220 word culturally aware story behind the piece linking to Indian traditions, religion, or community (as relevant).\n3) Suggestions for colors, symbols, and medium.\n\nReturn the three parts separated by a line containing only '---'. Always output in English."
    return prompt