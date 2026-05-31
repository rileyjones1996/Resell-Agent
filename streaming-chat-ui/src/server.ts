import Anthropic from "@anthropic-ai/sdk";
import express, { Request, Response } from "express";
import path from "path";

const app = express();
const client = new Anthropic();

app.use(express.json());
app.use(express.static(path.join(__dirname, "../public")));

interface ChatRequest {
  message: string;
  history: Anthropic.MessageParam[];
}

app.post("/chat", async (req: Request, res: Response) => {
  const { message, history } = req.body as ChatRequest;

  if (!message?.trim()) {
    res.status(400).json({ error: "Message is required" });
    return;
  }

  const messages: Anthropic.MessageParam[] = [
    ...history,
    { role: "user", content: message },
  ];

  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("Access-Control-Allow-Origin", "*");

  try {
    const stream = client.messages.stream({
      model: "claude-opus-4-8",
      max_tokens: 64000,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      thinking: { type: "adaptive" } as any,
      messages,
    });

    stream.on("text", (delta) => {
      res.write(`data: ${JSON.stringify({ type: "text", delta })}\n\n`);
    });

    const finalMessage = await stream.finalMessage();

    res.write(
      `data: ${JSON.stringify({
        type: "done",
        assistantMessage: finalMessage.content,
      })}\n\n`
    );
  } catch (err) {
    const error = err as Error;
    let message = "An error occurred";

    if (err instanceof Anthropic.RateLimitError) {
      message = "Rate limit reached. Please wait a moment and try again.";
    } else if (err instanceof Anthropic.AuthenticationError) {
      message = "Invalid API key. Check your ANTHROPIC_API_KEY.";
    } else if (err instanceof Anthropic.APIError) {
      message = `API error: ${error.message}`;
    }

    res.write(`data: ${JSON.stringify({ type: "error", message })}\n\n`);
  } finally {
    res.end();
  }
});

const PORT = process.env.PORT ?? 3000;
app.listen(PORT, () => {
  console.log(`Chat server running at http://localhost:${PORT}`);
  console.log("Set ANTHROPIC_API_KEY environment variable before starting.");
});
