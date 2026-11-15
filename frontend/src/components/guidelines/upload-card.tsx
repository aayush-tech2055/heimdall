"use client";

import { Loader2, Upload } from "lucide-react";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { GuidelineUploadResult } from "@/types/api";

/** Kinds of guideline file the backend can read (app/processing/documents.py). */
const GUIDELINE_FILES = [
  ".pdf",
  ".docx",
  ".pptx",
  ".txt",
  ".md",
  ".csv",
  ".tsv",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "text/plain",
  "text/markdown",
  "text/csv",
  "text/tab-separated-values",
].join(",");

export function UploadCard({
  brandId,
  onDone,
}: {
  brandId: string;
  onDone: (result: GuidelineUploadResult) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [mode, setMode] = useState("file");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const form = new FormData();
    if (mode === "file") {
      if (!file) return setError("Choose a file first.");
      form.append("file", file);
    } else {
      if (!text.trim()) return setError("Paste some guideline text first.");
      form.append("text", text);
    }
    setBusy(true);
    try {
      onDone(
        await api<GuidelineUploadResult>(`/brands/${brandId}/guidelines`, {
          form,
        }),
      );
      setFile(null);
      setText("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Upload guidelines</h2>
        </CardTitle>
        <CardDescription>
          Heimdall splits the guideline into one rule per instruction, then
          checks it for duplicates, contradictions, vague rules and missing
          categories. New rules stay pending until you approve them.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <Tabs value={mode} onValueChange={setMode}>
            <TabsList>
              <TabsTrigger value="file">Upload a file</TabsTrigger>
              <TabsTrigger value="text">Paste text</TabsTrigger>
            </TabsList>
            <TabsContent value="file" className="space-y-2 pt-2">
              <Label htmlFor="guideline-file">Guideline file</Label>
              <Input
                id="guideline-file"
                type="file"
                accept={GUIDELINE_FILES}
                aria-describedby="guideline-file-help"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <p
                id="guideline-file-help"
                className="text-sm text-muted-foreground"
              >
                PDF, Word (.docx), PowerPoint (.pptx), text (.txt, .md) or CSV,
                up to 10 MB. For a CSV, put one rule per row; a header row such
                as &ldquo;Category, Rule&rdquo; helps.
              </p>
            </TabsContent>
            <TabsContent value="text" className="space-y-2 pt-2">
              <Label htmlFor="guideline-text">Guideline text</Label>
              <Textarea
                id="guideline-text"
                rows={8}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste the brand guideline here…"
              />
            </TabsContent>
          </Tabs>
          {error && (
            <Alert variant="destructive" role="alert">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <Button type="submit" disabled={busy}>
            {busy ? (
              <Loader2 className="animate-spin" aria-hidden />
            ) : (
              <Upload aria-hidden />
            )}
            {busy
              ? "Extracting and checking rules… (about a minute)"
              : "Upload and extract rules"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
