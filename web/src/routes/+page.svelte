<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Textarea } from "$lib/components/ui/textarea";
  import * as Card from "$lib/components/ui/card";
  import { marked } from "marked";
  import DOMPurify from "isomorphic-dompurify";

  const API = "http://localhost:8000";

  let prompt = $state("");
  let response = $state("");
  let loading = $state(false);
  let error = $state("");

  const renderedMarkdown = $derived.by(() => {
    if (!response) return "";
    const html = marked.parse(response) as string;
    return DOMPurify.sanitize(html);
  });

  async function submit() {
    if (!prompt.trim()) return;
    loading = true;
    error = "";
    response = "";

    try {
      const res = await fetch(`${API}/prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(detail.detail ?? res.statusText);
      }

      const data = await res.json();
      response = data.response;
    } catch (e: any) {
      error = e.message ?? "Something went wrong";
    } finally {
      loading = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
  }
</script>

<div class="mx-auto max-w-2xl space-y-6 p-6">
  <Card.Root>
    <Card.Header>
      <Card.Title>Send Prompt</Card.Title>
    </Card.Header>
    <Card.Content class="space-y-4">
      <Textarea
        bind:value={prompt}
        placeholder="Enter your prompt... (Cmd+Enter to submit)"
        rows={4}
        onkeydown={handleKeydown}
      />
      <Button onclick={submit} disabled={loading || !prompt.trim()}>
        {loading ? "Thinking..." : "Submit"}
      </Button>
      {#if error}
        <p class="text-sm text-red-500">{error}</p>
      {/if}
    </Card.Content>
  </Card.Root>

  {#if response || loading}
    <Card.Root>
      <Card.Header>
        <Card.Title>Response</Card.Title>
      </Card.Header>
      <Card.Content>
        {#if loading}
          <p class="text-sm text-muted-foreground">Waiting...</p>
        {:else}
          <div
            class="prose prose-neutral max-w-none break-words dark:prose-invert"
          >
            {@html renderedMarkdown}
          </div>
        {/if}
      </Card.Content>
    </Card.Root>
  {/if}
</div>