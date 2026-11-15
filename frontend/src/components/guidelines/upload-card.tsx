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

export function UploadCard({
  brandId,
  onDone,
}: {
  brandId: string;
  onDone: (result: GuidelineUploadResult) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [mode, setMode] = useState("pdf");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const form = new FormData();
    if (mode === "pdf") {
      if (!file) return setError("Choose a PDF first.");
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
              <TabsTrigger value="pdf">PDF</TabsTrigger>
              <TabsTrigger value="text">Paste text</TabsTrigger>
            </TabsList>
            <TabsContent value="pdf" className="space-y-2 pt-2">
              <Label htmlFor="guideline-file">
                Guideline PDF (up to 10 MB)
              </Label>
              <Input
                id="guideline-file"
                type="file"
                accept="application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
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
