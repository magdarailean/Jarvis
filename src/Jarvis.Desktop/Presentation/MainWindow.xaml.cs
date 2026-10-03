using System.Windows;
using Jarvis.Desktop.Infrastructure;

namespace Jarvis.Desktop.Presentation;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        Loaded += (_, _) => AppLog.Write("Main window loaded; state=Ready.");
    }

    private void CloseButton_Click(object sender, RoutedEventArgs e) => Close();
}
