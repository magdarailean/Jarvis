using System.Globalization;
using System.Windows;
using System.Windows.Markup;
using Jarvis.Desktop.Infrastructure;

namespace Jarvis.Desktop;

public partial class App : System.Windows.Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        var culture = CultureInfo.GetCultureInfo("ro-RO");
        CultureInfo.DefaultThreadCurrentCulture = culture;
        CultureInfo.DefaultThreadCurrentUICulture = culture;
        FrameworkElement.LanguageProperty.OverrideMetadata(
            typeof(FrameworkElement),
            new FrameworkPropertyMetadata(XmlLanguage.GetLanguage(culture.IetfLanguageTag)));

        AppLog.Write("Application starting; milestone=0; capture=false; microphone=false.");
        base.OnStartup(e);
    }

    protected override void OnExit(ExitEventArgs e)
    {
        AppLog.Write($"Application stopped; exitCode={e.ApplicationExitCode}.");
        base.OnExit(e);
    }
}
