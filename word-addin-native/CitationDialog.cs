using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Workmode.WordAddin
{
    internal sealed class CitationDialog : Form
    {
        [DllImport("user32.dll")]
        private static extern uint GetDpiForWindow(IntPtr windowHandle);

        [DllImport("user32.dll")]
        private static extern uint GetDpiForSystem();

        private readonly float dpiScale;
        private readonly TabControl tabs;
        private readonly TabPage insertTab;
        private readonly TabPage manageTab;
        private readonly Label projectLabel;
        private readonly ComboBox styleBox;
        private readonly TextBox searchBox;
        private readonly CheckedListBox paperList;
        private readonly TextBox prefixBox;
        private readonly TextBox suffixBox;
        private readonly ComboBox locatorLabelBox;
        private readonly TextBox locatorValueBox;
        private readonly CheckBox suppressAuthorBox;
        private readonly Label statusLabel;
        private readonly ListBox citationList;

        public CitationDialog(bool manage)
        {
            AutoScaleMode = AutoScaleMode.None;
            Font = new Font("Microsoft YaHei UI", 9F);
            Text = "Workmode 引用";
            StartPosition = FormStartPosition.CenterParent;
            IntPtr wordWindow = Process.GetCurrentProcess().MainWindowHandle;
            dpiScale = ResolveDpiScale(wordWindow);
            Rectangle workingArea = Screen.FromHandle(wordWindow).WorkingArea;
            int safeWidth = Math.Max(ScalePixel(480), workingArea.Width - ScalePixel(48));
            int safeHeight = Math.Max(ScalePixel(400), workingArea.Height - ScalePixel(48));
            ClientSize = new Size(
                Math.Min(ScalePixel(900), safeWidth),
                Math.Min(ScalePixel(680), safeHeight));
            MinimumSize = new Size(
                Math.Min(ScalePixel(780), safeWidth),
                Math.Min(ScalePixel(600), safeHeight));

            projectLabel = new Label();
            projectLabel.AutoSize = false;
            projectLabel.Dock = DockStyle.Fill;
            projectLabel.TextAlign = ContentAlignment.MiddleLeft;
            projectLabel.Text = "正在连接 Workmode…";

            Label styleLabel = MakeLabel("引文样式");
            styleLabel.AutoSize = false;
            styleLabel.Dock = DockStyle.Left;
            styleLabel.Width = ScalePixel(78);
            styleLabel.TextAlign = ContentAlignment.MiddleRight;

            styleBox = new ComboBox();
            styleBox.DropDownStyle = ComboBoxStyle.DropDownList;
            styleBox.Dock = DockStyle.Fill;
            styleBox.SelectedIndexChanged += delegate
            {
                StyleOption selected = styleBox.SelectedItem as StyleOption;
                if (selected != null)
                {
                    NativeSettings.StyleId = selected.id;
                }
            };

            Panel stylePanel = new Panel();
            stylePanel.Dock = DockStyle.Right;
            stylePanel.Width = ScalePixel(330);
            stylePanel.Controls.Add(styleBox);
            stylePanel.Controls.Add(styleLabel);

            Panel headerPanel = new Panel();
            headerPanel.Dock = DockStyle.Top;
            headerPanel.Height = ScalePixel(48);
            headerPanel.Padding = new Padding(
                ScalePixel(14),
                ScalePixel(9),
                ScalePixel(14),
                ScalePixel(7));
            headerPanel.Controls.Add(projectLabel);
            headerPanel.Controls.Add(stylePanel);

            tabs = new TabControl();
            tabs.Dock = DockStyle.Fill;

            insertTab = new TabPage("插入引文");
            insertTab.Padding = new Padding(ScalePixel(14));
            manageTab = new TabPage("管理当前文档");
            manageTab.Padding = new Padding(ScalePixel(14));
            tabs.TabPages.Add(insertTab);
            tabs.TabPages.Add(manageTab);

            Label insertGuide = MakeLabel(
                "搜索并勾选文献，然后点击右下角「插入所选文献」。");
            insertGuide.AutoSize = false;
            insertGuide.Dock = DockStyle.Top;
            insertGuide.Height = ScalePixel(34);
            insertGuide.TextAlign = ContentAlignment.MiddleLeft;
            insertGuide.ForeColor = SystemColors.GrayText;

            searchBox = new TextBox();
            searchBox.Dock = DockStyle.Fill;
            searchBox.KeyDown += async delegate(object sender, KeyEventArgs args)
            {
                if (args.KeyCode == Keys.Enter)
                {
                    await SearchPapersAsync();
                    args.SuppressKeyPress = true;
                }
            };

            Button searchButton = new Button();
            searchButton.Text = "搜索";
            searchButton.Dock = DockStyle.Right;
            searchButton.Width = ScalePixel(96);
            searchButton.Click += async delegate { await SearchPapersAsync(); };

            Panel searchPanel = new Panel();
            searchPanel.Dock = DockStyle.Top;
            searchPanel.Height = ScalePixel(40);
            searchPanel.Padding = new Padding(0, ScalePixel(4), 0, ScalePixel(4));
            searchPanel.Controls.Add(searchBox);
            searchPanel.Controls.Add(searchButton);

            paperList = new CheckedListBox();
            paperList.CheckOnClick = true;
            paperList.Dock = DockStyle.Fill;
            paperList.IntegralHeight = false;
            paperList.HorizontalScrollbar = true;
            paperList.Font = new Font("Microsoft YaHei UI", 9.5F);

            locatorLabelBox = new ComboBox();
            locatorLabelBox.DropDownStyle = ComboBoxStyle.DropDownList;
            locatorLabelBox.Width = ScalePixel(110);
            locatorLabelBox.Items.Add(new LocatorOption("page", "页码"));
            locatorLabelBox.Items.Add(new LocatorOption("chapter", "章节"));
            locatorLabelBox.Items.Add(new LocatorOption("section", "小节"));
            locatorLabelBox.Items.Add(new LocatorOption("figure", "图"));
            locatorLabelBox.Items.Add(new LocatorOption("table", "表"));
            locatorLabelBox.SelectedIndex = 0;

            locatorValueBox = new TextBox();
            locatorValueBox.Width = ScalePixel(160);

            suppressAuthorBox = new CheckBox();
            suppressAuthorBox.Text = "隐藏作者";
            suppressAuthorBox.AutoSize = true;
            suppressAuthorBox.Margin = new Padding(ScalePixel(16), ScalePixel(5), 0, 0);

            FlowLayoutPanel locatorRow = new FlowLayoutPanel();
            locatorRow.Dock = DockStyle.Top;
            locatorRow.Height = ScalePixel(40);
            locatorRow.WrapContents = false;
            locatorRow.FlowDirection = FlowDirection.LeftToRight;
            locatorRow.Controls.Add(MakeFlowLabel("定位（可选）", ScalePixel(92)));
            locatorRow.Controls.Add(locatorLabelBox);
            locatorRow.Controls.Add(locatorValueBox);
            locatorRow.Controls.Add(suppressAuthorBox);

            prefixBox = new TextBox();
            prefixBox.Width = ScalePixel(230);
            suffixBox = new TextBox();
            suffixBox.Width = ScalePixel(230);

            FlowLayoutPanel affixRow = new FlowLayoutPanel();
            affixRow.Dock = DockStyle.Top;
            affixRow.Height = ScalePixel(40);
            affixRow.WrapContents = false;
            affixRow.FlowDirection = FlowDirection.LeftToRight;
            affixRow.Controls.Add(MakeFlowLabel("前缀（可选）", ScalePixel(92)));
            affixRow.Controls.Add(prefixBox);
            affixRow.Controls.Add(MakeFlowLabel("后缀（可选）", ScalePixel(92)));
            affixRow.Controls.Add(suffixBox);

            Button insertButton = new Button();
            insertButton.Text = "插入所选文献";
            insertButton.Dock = DockStyle.Right;
            insertButton.Width = ScalePixel(166);
            insertButton.Click += async delegate { await InsertSelectedPapersAsync(); };

            statusLabel = new Label();
            statusLabel.AutoSize = false;
            statusLabel.Dock = DockStyle.Fill;
            statusLabel.TextAlign = ContentAlignment.MiddleLeft;

            Panel actionRow = new Panel();
            actionRow.Dock = DockStyle.Fill;
            actionRow.Padding = new Padding(0, ScalePixel(4), 0, 0);
            actionRow.Controls.Add(statusLabel);
            actionRow.Controls.Add(insertButton);

            Panel optionsPanel = new Panel();
            optionsPanel.Dock = DockStyle.Bottom;
            optionsPanel.Height = ScalePixel(132);
            optionsPanel.Padding = new Padding(0, ScalePixel(8), 0, 0);
            optionsPanel.Controls.Add(actionRow);
            optionsPanel.Controls.Add(affixRow);
            optionsPanel.Controls.Add(locatorRow);

            insertTab.Controls.Add(paperList);
            insertTab.Controls.Add(optionsPanel);
            insertTab.Controls.Add(searchPanel);
            insertTab.Controls.Add(insertGuide);

            citationList = new ListBox();
            citationList.Dock = DockStyle.Fill;
            citationList.HorizontalScrollbar = true;

            Button reloadButton = new Button();
            reloadButton.Text = "重新读取";
            reloadButton.Dock = DockStyle.Left;
            reloadButton.Width = ScalePixel(112);
            reloadButton.Click += async delegate { await LoadCitationsAsync(); };

            Button removeButton = new Button();
            removeButton.Text = "移除所选引文";
            removeButton.Dock = DockStyle.Right;
            removeButton.Width = ScalePixel(150);
            removeButton.Click += async delegate { await RemoveSelectedCitationAsync(); };

            Panel manageActions = new Panel();
            manageActions.Dock = DockStyle.Bottom;
            manageActions.Height = ScalePixel(48);
            manageActions.Padding = new Padding(0, ScalePixel(8), 0, 0);
            manageActions.Controls.Add(reloadButton);
            manageActions.Controls.Add(removeButton);

            manageTab.Controls.Add(citationList);
            manageTab.Controls.Add(manageActions);

            Button closeButton = new Button();
            closeButton.Text = "关闭";
            closeButton.Dock = DockStyle.Right;
            closeButton.Width = ScalePixel(110);
            closeButton.Click += delegate { Close(); };

            Panel footerPanel = new Panel();
            footerPanel.Dock = DockStyle.Bottom;
            footerPanel.Height = ScalePixel(50);
            footerPanel.Padding = new Padding(
                ScalePixel(14),
                ScalePixel(7),
                ScalePixel(14),
                ScalePixel(9));
            footerPanel.Controls.Add(closeButton);

            Controls.Add(tabs);
            Controls.Add(footerPanel);
            Controls.Add(headerPanel);

            Shown += async delegate
            {
                tabs.SelectedTab = manage ? manageTab : insertTab;
                await LoadWorkspaceAsync(manage);
            };
        }

        private static float ResolveDpiScale(IntPtr wordWindow)
        {
            try
            {
                uint dpi = GetDpiForWindow(wordWindow);
                if (dpi < 96)
                {
                    dpi = GetDpiForSystem();
                }
                if (dpi >= 96)
                {
                    return Math.Min(3F, dpi / 96F);
                }
            }
            catch (DllNotFoundException)
            {
            }
            catch (EntryPointNotFoundException)
            {
            }
            return 1F;
        }

        private int ScalePixel(int value)
        {
            return Math.Max(1, (int)Math.Round(value * dpiScale));
        }

        private static Label MakeLabel(string text)
        {
            Label label = new Label();
            label.Text = text;
            label.AutoSize = true;
            return label;
        }

        private static Label MakeFlowLabel(string text, int width)
        {
            Label label = MakeLabel(text);
            label.AutoSize = false;
            label.Width = width;
            label.Height = 28;
            label.TextAlign = ContentAlignment.MiddleLeft;
            return label;
        }

        private async Task LoadWorkspaceAsync(bool manage)
        {
            try
            {
                UseWaitCursor = true;
                SetStatus("正在载入文献库，请稍候…", false);
                BootstrapResponse response =
                    await ApiClient.GetAsync<BootstrapResponse>("/bootstrap");
                projectLabel.Text = "当前文献库：" + response.project.name;
                styleBox.Items.Clear();
                foreach (StyleOption style in response.styles)
                {
                    styleBox.Items.Add(style);
                }
                StyleOption activeStyle = response.styles.FirstOrDefault(
                    delegate(StyleOption item) { return item.id == NativeSettings.StyleId; });
                styleBox.SelectedItem = activeStyle ?? response.styles.FirstOrDefault();
                await SearchPapersAsync();
                if (manage)
                {
                    await LoadCitationsAsync();
                }
            }
            catch (Exception error)
            {
                MessageBox.Show(error.Message, "Workmode", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            finally
            {
                UseWaitCursor = false;
            }
        }

        private async Task SearchPapersAsync()
        {
            try
            {
                UseWaitCursor = true;
                SetStatus("正在搜索文献…", false);
                PapersResponse response = await ApiClient.GetAsync<PapersResponse>(
                    "/papers?query=" + Uri.EscapeDataString(searchBox.Text.Trim()) + "&limit=100");
                paperList.Items.Clear();
                foreach (Paper paper in response.papers)
                {
                    paperList.Items.Add(paper, false);
                }
                SetStatus("找到 " + response.papers.Length + " 篇文献。", false);
            }
            catch (Exception error)
            {
                SetStatus(error.Message, true);
            }
            finally
            {
                UseWaitCursor = false;
            }
        }

        private async Task InsertSelectedPapersAsync()
        {
            List<string> paperIds = new List<string>();
            foreach (object item in paperList.CheckedItems)
            {
                Paper paper = item as Paper;
                if (paper != null)
                {
                    paperIds.Add(paper.id);
                }
            }
            if (paperIds.Count == 0)
            {
                SetStatus("请先勾选至少一篇文献。", true);
                return;
            }

            try
            {
                UseWaitCursor = true;
                LocatorOption locator = locatorLabelBox.SelectedItem as LocatorOption;
                Dictionary<string, object> body = new Dictionary<string, object>();
                body["paper_ids"] = paperIds.ToArray();
                body["style_id"] = SelectedStyleId();
                body["prefix"] = prefixBox.Text;
                body["suffix"] = suffixBox.Text;
                body["locator_label"] = String.IsNullOrWhiteSpace(locatorValueBox.Text)
                    ? null
                    : (locator == null ? "page" : locator.Id);
                body["locator_value"] = locatorValueBox.Text.Trim();
                body["suppress_author"] = suppressAuthorBox.Checked;
                SetStatus("正在插入引文，请稍候…", false);
                Dictionary<string, object> result =
                    await ApiClient.PostAsync<Dictionary<string, object>>("/citations", body);
                SetStatus(
                    "已插入引文。当前文档共 "
                        + ResultValue(result, "citation_count")
                        + " 处引用。",
                    false);
                for (int index = 0; index < paperList.Items.Count; index++)
                {
                    paperList.SetItemChecked(index, false);
                }
            }
            catch (Exception error)
            {
                SetStatus(error.Message, true);
            }
            finally
            {
                UseWaitCursor = false;
            }
        }

        private async Task LoadCitationsAsync()
        {
            try
            {
                citationList.Items.Clear();
                citationList.Items.Add(new CitationGroup
                {
                    text = "正在读取当前文档中的引用…",
                    instance_id = String.Empty
                });
                InspectResponse response =
                    await ApiClient.GetAsync<InspectResponse>("/citations/inspect");
                citationList.Items.Clear();
                foreach (CitationGroup group in response.citation_groups)
                {
                    citationList.Items.Add(group);
                }
                if (response.citation_groups.Length == 0)
                {
                    citationList.Items.Add(new CitationGroup
                    {
                        text = "当前文档还没有 Workmode 引文。",
                        instance_id = String.Empty
                    });
                }
                if (!String.IsNullOrWhiteSpace(response.style_id))
                {
                    NativeSettings.StyleId = response.style_id;
                }
            }
            catch (Exception error)
            {
                citationList.Items.Clear();
                citationList.Items.Add(new CitationGroup
                {
                    text = error.Message,
                    instance_id = String.Empty
                });
            }
        }

        private async Task RemoveSelectedCitationAsync()
        {
            CitationGroup group = citationList.SelectedItem as CitationGroup;
            if (group == null || String.IsNullOrWhiteSpace(group.instance_id))
            {
                MessageBox.Show(
                    "请先选择要移除的引文。",
                    "Workmode",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information);
                return;
            }
            if (MessageBox.Show(
                    "确定从当前文档移除这条引文吗？" + Environment.NewLine + group.text,
                    "Workmode",
                    MessageBoxButtons.YesNo,
                    MessageBoxIcon.Question) != DialogResult.Yes)
            {
                return;
            }
            try
            {
                await ApiClient.PostAsync<Dictionary<string, object>>(
                    "/citations/remove",
                    new Dictionary<string, object>
                    {
                        { "instance_id", group.instance_id },
                        { "style_id", SelectedStyleId() }
                    });
                await LoadCitationsAsync();
            }
            catch (Exception error)
            {
                MessageBox.Show(
                    error.Message,
                    "Workmode",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning);
            }
        }

        private string SelectedStyleId()
        {
            StyleOption style = styleBox.SelectedItem as StyleOption;
            return style == null ? NativeSettings.StyleId : style.id;
        }

        private void SetStatus(string message, bool error)
        {
            statusLabel.Text = message;
            statusLabel.ForeColor = error ? Color.Firebrick : Color.DarkGreen;
        }

        private static string ResultValue(Dictionary<string, object> result, string name)
        {
            object value;
            return result != null && result.TryGetValue(name, out value) && value != null
                ? Convert.ToString(value)
                : "0";
        }
    }

    internal sealed class BootstrapResponse
    {
        public ProjectInfo project { get; set; }
        public StyleOption[] styles { get; set; }
    }

    internal sealed class ProjectInfo
    {
        public string slug { get; set; }
        public string name { get; set; }
    }

    internal sealed class StyleOption
    {
        public string id { get; set; }
        public string label { get; set; }
        public string kind { get; set; }

        public override string ToString()
        {
            return label;
        }
    }

    internal sealed class PapersResponse
    {
        public Paper[] papers { get; set; }
    }

    internal sealed class Paper
    {
        public string id { get; set; }
        public string title { get; set; }
        public string authors { get; set; }
        public string journal { get; set; }
        public object year { get; set; }
        public string doi { get; set; }
        public string[] tags { get; set; }
        public string[] groups { get; set; }

        public override string ToString()
        {
            string metadata = String.Join(" · ", new[]
            {
                authors,
                journal,
                year == null ? null : Convert.ToString(year)
            }.Where(delegate(string item) { return !String.IsNullOrWhiteSpace(item); }));
            return String.IsNullOrWhiteSpace(metadata) ? title : title + "  —  " + metadata;
        }
    }

    internal sealed class InspectResponse
    {
        public CitationGroup[] citation_groups { get; set; }
        public string style_id { get; set; }
    }

    internal sealed class CitationGroup
    {
        public string instance_id { get; set; }
        public string text { get; set; }

        public override string ToString()
        {
            return String.IsNullOrWhiteSpace(text) ? "Workmode 引文 " + instance_id : text;
        }
    }

    internal sealed class LocatorOption
    {
        public readonly string Id;
        private readonly string label;

        public LocatorOption(string id, string displayLabel)
        {
            Id = id;
            label = displayLabel;
        }

        public override string ToString()
        {
            return label;
        }
    }
}
