using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using System.Windows;
using Flow.Launcher.Plugin;

namespace Findmyfiles.FlowLauncher.Plugin;

public sealed class Main : IPlugin, IContextMenu
{
    private const string PluginName = "Findmyfiles";
    private const string DefaultApiBaseUrl = "http://127.0.0.1:7474";
    private const int DefaultResultCount = 8;

    private static readonly HttpClient HttpClient = new()
    {
        Timeout = TimeSpan.FromSeconds(3),
    };

    private PluginInitContext? _context;
    private string? _iconPath;
    private string _apiBaseUrl = DefaultApiBaseUrl;

    public string Name => PluginName;

    public string Description => "Search files indexed by the local findmyfiles service.";

    public void Init(PluginInitContext context)
    {
        _context = context ?? throw new ArgumentNullException(nameof(context));
        _iconPath = context.CurrentPluginMetadata.IcoPath;
    }

    public List<Result> Query(Query query)
    {
        ArgumentNullException.ThrowIfNull(query);

        var search = (query.Search ?? string.Empty).Trim();
        if (string.IsNullOrWhiteSpace(search))
        {
            return BuildIdleResults();
        }

        try
        {
            var request = new SearchRequest(search, DefaultResultCount, null);
            using var response = HttpClient.PostAsJsonAsync($"{_apiBaseUrl}/search", request).GetAwaiter().GetResult();
            if (!response.IsSuccessStatusCode)
            {
                return BuildServiceErrorResults(
                    $"Search failed with HTTP {(int)response.StatusCode}",
                    "The service responded but did not accept the search request.",
                    canOpenDocs: true
                );
            }

            var payload = response.Content.ReadFromJsonAsync<SearchResponse>().GetAwaiter().GetResult();
            if (payload?.Results is null || payload.Results.Count == 0)
            {
                return
                [
                    new Result
                    {
                        Title = $"No indexed matches for \"{search}\"",
                        SubTitle = "Try a broader query or make sure the file was indexed first.",
                        IcoPath = _iconPath,
                        Action = _ => false,
                    }
                ];
            }

            return payload.Results.Select(BuildSearchResult).ToList();
        }
        catch (Exception ex)
        {
            return BuildServiceErrorResults(
                "findmyfiles service is unavailable",
                $"Could not reach {_apiBaseUrl}. {ex.Message}",
                canOpenDocs: true
            );
        }
    }

    public List<Result> LoadContextMenus(Result selectedResult)
    {
        if (selectedResult?.ContextData is not SearchResultItem item)
        {
            return [];
        }

        return
        [
            new Result
            {
                Title = "Open (Enter)",
                SubTitle = item.Path,
                IcoPath = _iconPath,
                Action = _ => OpenPath(item.Path),
            },
            new Result
            {
                Title = "Reveal in Explorer (Ctrl+Enter)",
                SubTitle = item.Path,
                IcoPath = _iconPath,
                Action = _ => RevealInExplorer(item.Path),
            },
            new Result
            {
                Title = "Copy path (Alt+Enter)",
                SubTitle = item.Path,
                IcoPath = _iconPath,
                Action = _ => CopyToClipboard(item.Path),
            },
            new Result
            {
                Title = "Re-index file",
                SubTitle = item.Path,
                IcoPath = _iconPath,
                Action = _ => ReindexPath(item.Path),
            }
        ];
    }

    private List<Result> BuildIdleResults()
    {
        var healthSubtitle = CheckHealth();
        return
        [
            new Result
            {
                Title = "Type to search indexed files",
                SubTitle = "Example: fmf invoice march or fmf project notes",
                IcoPath = _iconPath,
                Action = _ => false,
            },
            new Result
            {
                Title = "Service status",
                SubTitle = healthSubtitle,
                IcoPath = _iconPath,
                Action = _ => OpenUrl($"{_apiBaseUrl}/docs"),
            }
        ];
    }

    private string CheckHealth()
    {
        try
        {
            using var response = HttpClient.GetAsync($"{_apiBaseUrl}/health").GetAwaiter().GetResult();
            if (!response.IsSuccessStatusCode)
            {
                return $"API unhealthy at {_apiBaseUrl}";
            }

            var payload = response.Content.ReadFromJsonAsync<HealthResponse>().GetAwaiter().GetResult();
            var stats = payload?.Stats;
            if (stats is null)
            {
                return $"API reachable at {_apiBaseUrl}";
            }

            return $"Running at {_apiBaseUrl} | {stats.Documents} files | {stats.Chunks} chunks";
        }
        catch
        {
            return $"Offline at {_apiBaseUrl}. Start `findmyfiles` before using the plugin.";
        }
    }

    private Result BuildSearchResult(SearchResultItem item)
    {
        var title = Path.GetFileName(item.Path);
        var snippet = string.IsNullOrWhiteSpace(item.Snippet) ? item.Path : item.Snippet.Trim();
        var subtitle = $"{item.Mime} | score {item.Score:F2} | {snippet}";

        return new Result
        {
            Title = string.IsNullOrWhiteSpace(title) ? item.Path : title,
            SubTitle = subtitle,
            IcoPath = _iconPath,
            ContextData = item,
            Action = _ => OpenPath(item.Path),
        };
    }

    private List<Result> BuildServiceErrorResults(string title, string subtitle, bool canOpenDocs)
    {
        var results =
            new List<Result>
            {
                new()
                {
                    Title = title,
                    SubTitle = subtitle,
                    IcoPath = _iconPath,
                    Action = _ => false,
                }
            };

        if (canOpenDocs)
        {
            results.Add(
                new Result
                {
                    Title = "Open API docs",
                    SubTitle = $"{_apiBaseUrl}/docs",
                    IcoPath = _iconPath,
                    Action = _ => OpenUrl($"{_apiBaseUrl}/docs"),
                }
            );
        }

        return results;
    }

    private bool ReindexPath(string path)
    {
        try
        {
            using var response = HttpClient.PostAsJsonAsync($"{_apiBaseUrl}/index", new IndexRequest(path)).GetAwaiter().GetResult();
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    private static bool OpenPath(string path)
    {
        try
        {
            Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
            return true;
        }
        catch
        {
            return false;
        }
    }

    private static bool RevealInExplorer(string path)
    {
        try
        {
            Process.Start(new ProcessStartInfo("explorer.exe", $"/select,\"{path}\"") { UseShellExecute = true });
            return true;
        }
        catch
        {
            return false;
        }
    }

    private static bool CopyToClipboard(string value)
    {
        try
        {
            Clipboard.SetText(value);
            return true;
        }
        catch
        {
            return false;
        }
    }

    private static bool OpenUrl(string url)
    {
        try
        {
            Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            return true;
        }
        catch
        {
            return false;
        }
    }

    private sealed record SearchRequest(
        [property: JsonPropertyName("query")] string Query,
        [property: JsonPropertyName("n_results")] int ResultCount,
        [property: JsonPropertyName("filters")] object? Filters
    );

    private sealed record IndexRequest([property: JsonPropertyName("path")] string Path);

    private sealed record SearchResponse(
        [property: JsonPropertyName("results")] List<SearchResultItem> Results
    );

    private sealed record SearchResultItem(
        [property: JsonPropertyName("path")] string Path,
        [property: JsonPropertyName("score")] double Score,
        [property: JsonPropertyName("chunk")] int Chunk,
        [property: JsonPropertyName("snippet")] string Snippet,
        [property: JsonPropertyName("mime")] string Mime,
        [property: JsonPropertyName("size")] long Size,
        [property: JsonPropertyName("mtime")] double Mtime
    );

    private sealed record HealthResponse(
        [property: JsonPropertyName("status")] string Status,
        [property: JsonPropertyName("stats")] HealthStats Stats
    );

    private sealed record HealthStats(
        [property: JsonPropertyName("documents")] int Documents,
        [property: JsonPropertyName("chunks")] int Chunks
    );
}
