using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Extensibility;
using Office = Microsoft.Office.Core;

[assembly: ComVisible(true)]
[assembly: Guid("d2fb41ad-9367-4dbf-a653-354bd45a4295")]
[assembly: AssemblyTitle("Workmode Word Add-in")]
[assembly: AssemblyDescription("Native Microsoft Word ribbon for Workmode Public")]
[assembly: AssemblyCompany("Workmode Public")]
[assembly: AssemblyProduct("Workmode Public")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

namespace Workmode.WordAddin
{
    [ComVisible(true)]
    [Guid("9a7bc47d-8d3b-4bf8-a77a-7b84ee755c2b")]
    [ProgId("Workmode.WordAddin")]
    [ClassInterface(ClassInterfaceType.AutoDual)]
    public sealed class Connect : IDTExtensibility2, Office.IRibbonExtensibility
    {
        public string GetCustomUI(string ribbonId)
        {
            Assembly assembly = Assembly.GetExecutingAssembly();
            using (Stream stream = assembly.GetManifestResourceStream("Workmode.WordAddin.Ribbon.xml"))
            {
                if (stream == null)
                {
                    return String.Empty;
                }
                using (StreamReader reader = new StreamReader(stream, Encoding.UTF8))
                {
                    return reader.ReadToEnd();
                }
            }
        }

        public void InsertCitation(Office.IRibbonControl control)
        {
            ShowCitationDialog(false);
        }

        public void ManageCitations(Office.IRibbonControl control)
        {
            ShowCitationDialog(true);
        }

        public async void RefreshCitations(Office.IRibbonControl control)
        {
            await RunDocumentActionAsync(
                "/citations/refresh",
                NativeSettings.StyleId,
                "引文与参考文献已刷新。");
        }

        public async void CreateBibliography(Office.IRibbonControl control)
        {
            await RunDocumentActionAsync(
                "/bibliography",
                NativeSettings.StyleId,
                "参考文献已插入或刷新。");
        }

        public async void SetStyleGBT(Office.IRibbonControl control)
        {
            await SetStyleAsync("gb-t-7714-2015-numeric");
        }

        public async void SetStyleACS(Office.IRibbonControl control)
        {
            await SetStyleAsync("american-chemical-society");
        }

        public async void SetStyleNature(Office.IRibbonControl control)
        {
            await SetStyleAsync("nature");
        }

        public async void SetStyleAPA(Office.IRibbonControl control)
        {
            await SetStyleAsync("apa-7th");
        }

        public async void SetStyleVancouver(Office.IRibbonControl control)
        {
            await SetStyleAsync("vancouver");
        }

        private static async Task SetStyleAsync(string styleId)
        {
            NativeSettings.StyleId = styleId;
            await RunDocumentActionAsync(
                "/citations/refresh",
                styleId,
                "引文样式已应用并刷新全文。");
        }

        private static async Task RunDocumentActionAsync(
            string path,
            string styleId,
            string successMessage)
        {
            try
            {
                await ApiClient.PostAsync<Dictionary<string, object>>(
                    path,
                    new Dictionary<string, object>
                    {
                        { "style_id", styleId }
                    });
                MessageBox.Show(successMessage, "Workmode", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception error)
            {
                ShowError(error);
            }
        }

        private static void ShowCitationDialog(bool manage)
        {
            try
            {
                using (CitationDialog dialog = new CitationDialog(manage))
                {
                    dialog.ShowDialog(new WindowOwner(Process.GetCurrentProcess().MainWindowHandle));
                }
            }
            catch (Exception error)
            {
                ShowError(error);
            }
        }

        private static void ShowError(Exception error)
        {
            MessageBox.Show(
                error.Message + Environment.NewLine + Environment.NewLine + "请确认 Workmode 正在运行。",
                "Workmode",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning);
        }

        public void OnConnection(object application, ext_ConnectMode connectMode, object addInInst, ref Array custom)
        {
        }

        public void OnDisconnection(ext_DisconnectMode removeMode, ref Array custom)
        {
        }

        public void OnAddInsUpdate(ref Array custom)
        {
        }

        public void OnStartupComplete(ref Array custom)
        {
        }

        public void OnBeginShutdown(ref Array custom)
        {
        }
    }

    internal static class ApiClient
    {
        private const string BaseUrl = "http://127.0.0.1:8765/api/word-addin";

        public static Task<T> GetAsync<T>(string path)
        {
            return Task.Run(delegate { return Send<T>("GET", path, null); });
        }

        public static Task<T> PostAsync<T>(string path, object body)
        {
            string json = new JavaScriptSerializer().Serialize(body);
            return Task.Run(delegate { return Send<T>("POST", path, json); });
        }

        private static T Send<T>(string method, string path, string body)
        {
            try
            {
                using (TimeoutWebClient client = new TimeoutWebClient(
                    path.StartsWith("/citations", StringComparison.Ordinal)
                        || path == "/bibliography"
                        ? 35000
                        : 8000))
                {
                    client.Encoding = Encoding.UTF8;
                    client.Headers[HttpRequestHeader.Accept] = "application/json";
                    string token = NativeSettings.ReadApiToken();
                    if (!String.IsNullOrWhiteSpace(token))
                    {
                        client.Headers["X-Workmode-Token"] = token;
                    }
                    string json;
                    if (method == "POST")
                    {
                        client.Headers[HttpRequestHeader.ContentType] = "application/json";
                        json = client.UploadString(BaseUrl + path, "POST", body ?? "{}");
                    }
                    else
                    {
                        json = client.DownloadString(BaseUrl + path);
                    }
                    return new JavaScriptSerializer().Deserialize<T>(json);
                }
            }
            catch (WebException error)
            {
                if (error.Status == WebExceptionStatus.Timeout
                    || error.Status == WebExceptionStatus.RequestCanceled)
                {
                    throw new InvalidOperationException(
                        "Word 响应超时。请先关闭 Word 中其他弹窗，再重试一次。",
                        error);
                }
                string detail = ReadErrorDetail(error);
                throw new InvalidOperationException(
                    String.IsNullOrWhiteSpace(detail) ? "无法连接 Workmode 本地服务。" : detail,
                    error);
            }
        }

        private static string ReadErrorDetail(WebException error)
        {
            if (error.Response == null)
            {
                return error.Message;
            }
            try
            {
                using (Stream stream = error.Response.GetResponseStream())
                using (StreamReader reader = new StreamReader(stream, Encoding.UTF8))
                {
                    Dictionary<string, object> payload =
                        new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(
                            reader.ReadToEnd());
                    object detail;
                    return payload != null && payload.TryGetValue("detail", out detail)
                        ? Convert.ToString(detail)
                        : error.Message;
                }
            }
            catch
            {
                return error.Message;
            }
        }
    }

    internal sealed class TimeoutWebClient : WebClient
    {
        private readonly int timeoutMilliseconds;

        public TimeoutWebClient(int timeout)
        {
            timeoutMilliseconds = timeout;
        }

        protected override WebRequest GetWebRequest(Uri address)
        {
            WebRequest request = base.GetWebRequest(address);
            request.Timeout = timeoutMilliseconds;
            HttpWebRequest httpRequest = request as HttpWebRequest;
            if (httpRequest != null)
            {
                httpRequest.ReadWriteTimeout = timeoutMilliseconds;
            }
            return request;
        }
    }

    internal static class NativeSettings
    {
        private static string styleId = "gb-t-7714-2015-numeric";

        public static string StyleId
        {
            get { return styleId; }
            set
            {
                if (!String.IsNullOrWhiteSpace(value))
                {
                    styleId = value;
                }
            }
        }

        public static string ReadApiToken()
        {
            string environmentToken = Environment.GetEnvironmentVariable("WORKMODE_PUBLIC_TOKEN");
            if (!String.IsNullOrWhiteSpace(environmentToken))
            {
                return environmentToken.Trim();
            }
            string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            string envPath = Path.Combine(appData, "WorkmodePublic", "config", ".env");
            if (!File.Exists(envPath))
            {
                return String.Empty;
            }
            foreach (string rawLine in File.ReadAllLines(envPath, Encoding.UTF8))
            {
                string line = rawLine.Trim();
                if (line.StartsWith("WORKMODE_PUBLIC_TOKEN=", StringComparison.Ordinal))
                {
                    return line.Substring("WORKMODE_PUBLIC_TOKEN=".Length).Trim().Trim('"', '\'');
                }
            }
            return String.Empty;
        }
    }

    internal sealed class WindowOwner : IWin32Window
    {
        public WindowOwner(IntPtr handle)
        {
            Handle = handle;
        }

        public IntPtr Handle { get; private set; }
    }
}
