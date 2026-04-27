#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct Config {
    int m = 1000;
    int n = 1000;
    int q = 1000;
    std::vector<int> p_values {1, 4, 9, 16, 25};
    std::string csv_path = "benchmark_results.csv";
    std::string svg_path = "benchmark_results.svg";
    bool write_csv = true;
    bool write_svg = true;
};

struct CommandResult {
    int exit_code = -1;
    double seconds = std::numeric_limits<double>::quiet_NaN();
    std::string raw_output;
    std::string command;
};

struct BenchmarkRow {
    std::string implementation;
    std::string color;
    int m = 0;
    int n = 0;
    int q = 0;
    int p = 0;
    double seconds = std::numeric_limits<double>::quiet_NaN();
    double speedup = std::numeric_limits<double>::quiet_NaN();
    double serial_speedup = std::numeric_limits<double>::quiet_NaN();
    double cost = std::numeric_limits<double>::quiet_NaN();
    int exit_code = -1;
    std::string status;
    std::string command;
    std::string raw_output;
};

struct ImplementationInfo {
    std::string heading;
    std::string implementation_name;
    std::string color;
    std::string command_path;
    bool launch_with_mpi;
    bool is_serial;

    ImplementationInfo(
        const std::string& heading_value,
        const std::string& implementation_name_value,
        const std::string& color_value,
        const std::string& command_path_value,
        bool launch_with_mpi_value,
        bool is_serial_value
    ) : heading(heading_value),
        implementation_name(implementation_name_value),
        color(color_value),
        command_path(command_path_value),
        launch_with_mpi(launch_with_mpi_value),
        is_serial(is_serial_value){}
};

std::string trim(const std::string& value){
    const std::string whitespace = " \t\r\n";
    const std::size_t first = value.find_first_not_of(whitespace);
    if(first == std::string::npos){
        return "";
    }
    const std::size_t last = value.find_last_not_of(whitespace);
    return value.substr(first, last - first + 1);
}

int parse_positive_int(const std::string& text, const std::string& name){
    std::size_t parsed = 0;
    const long long value = std::stoll(text, &parsed);
    if(parsed != text.size() || value <= 0 || value > std::numeric_limits<int>::max()){
        throw std::invalid_argument("invalid value for " + name + ": " + text);
    }
    return static_cast<int>(value);
}

std::vector<int> parse_p_list(const std::string& text){
    std::vector<int> values;
    std::stringstream stream(text);
    std::string token;

    while(std::getline(stream, token, ',')){
        token = trim(token);
        if(!token.empty()) values.push_back(parse_positive_int(token, "p"));
    }

    if(values.empty()){
        throw std::invalid_argument("expected at least one P value");
    }

    return values;
}

void print_usage(const char* program_name){
    std::cout
        << "Usage: " << program_name << " [m n q] [--p=1,4,9] [--csv=path] [--svg=path] [--no-csv] [--no-svg]\n"
        << "Examples:\n"
        << "  " << program_name << '\n'
        << "  " << program_name << " 512 512 512 --p=1,4,9,16\n";
}

Config parse_args(int argc, char* argv[]){
    Config config;
    std::vector<std::string> positional;

    for(int i = 1; i < argc; ++i){
        const std::string arg = argv[i];
        if(arg == "--help" || arg == "-h"){ print_usage(argv[0]); std::exit(0); }
        if(arg == "--no-csv"){ config.write_csv = false; continue; }
        if(arg == "--no-svg"){ config.write_svg = false; continue; }
        if(arg.rfind("--p=", 0) == 0){ config.p_values = parse_p_list(arg.substr(4)); continue; }
        if(arg == "--p" && i + 1 < argc){ config.p_values = parse_p_list(argv[++i]); continue; }
        if(arg.rfind("--csv=", 0) == 0){ config.csv_path = arg.substr(6); continue; }
        if(arg == "--csv" && i + 1 < argc){ config.csv_path = argv[++i]; continue; }
        if(arg.rfind("--svg=", 0) == 0){ config.svg_path = arg.substr(6); continue; }
        if(arg == "--svg" && i + 1 < argc){ config.svg_path = argv[++i]; continue; }
        positional.push_back(arg);
    }

    if(!positional.empty()){
        if(positional.size() != 3){
            throw std::invalid_argument("expected either zero or three positional arguments: m n q");
        }
        config.m = parse_positive_int(positional[0], "m");
        config.n = parse_positive_int(positional[1], "n");
        config.q = parse_positive_int(positional[2], "q");
    }

    return config;
}

CommandResult run_command(const std::string& command){
    CommandResult result;
    result.command = command;

    FILE* pipe = popen((command + " 2>&1").c_str(), "r");
    if(pipe == nullptr){
        result.raw_output = "Failed to open command pipe";
        return result;
    }

    char buffer[512];
    while(fgets(buffer, sizeof(buffer), pipe) != nullptr) result.raw_output += buffer;
    

    result.exit_code = pclose(pipe);

    const std::vector<std::string> markers {
        "Parallel Time:",
        "Total Runtime:",
        "Time:"
    };

    for(const std::string& marker : markers){
        const std::size_t marker_pos = result.raw_output.find(marker);
        if(marker_pos == std::string::npos){
            continue;
        }

        std::size_t number_start = marker_pos + marker.size();
        while(number_start < result.raw_output.size() && std::isspace(static_cast<unsigned char>(result.raw_output[number_start]))){
            ++number_start;
        }

        std::size_t number_end = number_start;
        while(number_end < result.raw_output.size()){
            const char ch = result.raw_output[number_end];
            if((ch >= '0' && ch <= '9') || ch == '.' || ch == '-' || ch == '+' || ch == 'e' || ch == 'E'){
                ++number_end;
            } else {
                break;
            }
        }

        if(number_end > number_start){
            result.seconds = std::stod(result.raw_output.substr(number_start, number_end - number_start));
            break;
        }
    }

    return result;
}

std::string format_metric(double value){
    if(std::isnan(value)) return "-";
    
    std::ostringstream out;
    out << std::fixed << std::setprecision(6) << value;
    return out.str();
}

std::string csv_escape(const std::string& value){
    std::string escaped = "\"";
    for(char ch : value){
        if(ch == '"'){
            escaped += "\"\"";
        } else if(ch == '\n' || ch == '\r'){
            escaped += ' ';
        } else {
            escaped += ch;
        }
    }
    escaped += "\"";
    return escaped;
}

void write_csv(const std::string& path, const std::vector<BenchmarkRow>& rows){
    std::ofstream out(path);
    if(!out) throw std::runtime_error("failed to open CSV output: " + path);
    

    out << "implementation,m,n,q,p,seconds,speedup,serial_speedup,cost,exit_code,status,command,raw_output\n";
    for(const BenchmarkRow& row : rows){
        out << csv_escape(row.implementation) << ','
            << row.m << ','
            << row.n << ','
            << row.q << ','
            << row.p << ','
            << format_metric(row.seconds) << ','
            << format_metric(row.speedup) << ','
            << format_metric(row.serial_speedup) << ','
            << format_metric(row.cost) << ','
            << row.exit_code << ','
            << csv_escape(row.status) << ','
            << csv_escape(row.command) << ','
            << csv_escape(row.raw_output) << '\n';
    }
}

double scale_x(int p, int min_p, int max_p, double left, double width){
    if(max_p == min_p){
        return left + width / 2.0;
    }
    return left + width * static_cast<double>(p - min_p) / static_cast<double>(max_p - min_p);
}

double scale_y(double value, double min_value, double max_value, double top, double height){
    if(max_value <= min_value){
        return top + height / 2.0;
    }
    const double ratio = (value - min_value) / (max_value - min_value);
    return top + height - ratio * height;
}

double find_max_metric(const std::vector<BenchmarkRow>& rows, bool use_speedup, bool use_cost){
    double max_value = 0.0;
    for(const BenchmarkRow& row : rows){
        const double value = use_speedup ? row.speedup : use_cost ? row.cost : row.seconds;
        if(!std::isnan(value)){
            max_value = std::max(max_value, value);
        }
    }
    return max_value <= 0.0 ? 1.0 : max_value * 1.10;
}

void write_plot_panel(std::ostream& out, const std::vector<BenchmarkRow>& rows, const std::vector<int>& p_values, const std::string& title, bool use_speedup, bool use_cost, double origin_x, double origin_y, double width, double height){
    const double left = origin_x + 70.0; // 70 is left margin
    const double top = origin_y + 30.0;  // 30 is top margin
    const double plot_width = width - 140.0;    // 100 is left and right margin
    const double plot_height = height - 75.0;
    const double max_y = find_max_metric(rows, use_speedup, use_cost);
    const int min_p = *std::min_element(p_values.begin(), p_values.end());
    const int max_p = *std::max_element(p_values.begin(), p_values.end());

    out << "<g>\n";
    out << "<text x=\"" << (origin_x + width / 2.0) << "\" y=\"" << (origin_y + 18.0)
        << "\" text-anchor=\"middle\" font-size=\"18\" font-family=\"sans-serif\">" << title << "</text>\n";
    out << "<rect x=\"" << left << "\" y=\"" << top << "\" width=\"" << plot_width
        << "\" height=\"" << plot_height << "\" fill=\"#ffffff\" stroke=\"#cbd5e1\"/>\n";

    for(int tick = 0; tick <= 5; ++tick){
        const double value = max_y * tick / 5.0;
        const double y = scale_y(value, 0.0, max_y, top, plot_height);
        out << "<line x1=\"" << left << "\" y1=\"" << y << "\" x2=\"" << (left + plot_width)
            << "\" y2=\"" << y << "\" stroke=\"#e2e8f0\" stroke-dasharray=\"4,4\"/>\n";
        out << "<text x=\"" << (left - 10.0) << "\" y=\"" << (y + 4.0)
            << "\" text-anchor=\"end\" font-size=\"11\" font-family=\"monospace\">"
            << std::fixed << std::setprecision(3) << value << "</text>\n";
    }

    for(int p : p_values){
        const double x = scale_x(p, min_p, max_p, left, plot_width);
        out << "<line x1=\"" << x << "\" y1=\"" << top << "\" x2=\"" << x
            << "\" y2=\"" << (top + plot_height) << "\" stroke=\"#f1f5f9\"/>\n";
        out << "<text x=\"" << x << "\" y=\"" << (top + plot_height + 20.0)
            << "\" text-anchor=\"middle\" font-size=\"11\" font-family=\"monospace\">" << p << "</text>\n";
    }

    out << "<text x=\"" << (left + plot_width / 2.0) << "\" y=\"" << (top + plot_height + 45.0)
        << "\" text-anchor=\"middle\" font-size=\"12\" font-family=\"sans-serif\">P (threads / processors)</text>\n";
    out << "<text x=\"" << (origin_x + 18.0) << "\" y=\"" << (top + plot_height / 2.0)
        << "\" transform=\"rotate(-90 " << (origin_x + 10.0) << ' ' << (top + plot_height / 2.0)
        << ")\" text-anchor=\"middle\" font-size=\"12\" font-family=\"sans-serif\">"
        << (use_speedup ? "Speedup" : use_cost ? "Cost" : "Seconds") << "</text>\n";

    std::map<std::string, std::vector<const BenchmarkRow*> > grouped_rows;
    std::map<std::string, std::string> colors;
    for(const BenchmarkRow& row : rows){
        const double value = use_speedup ? row.speedup : use_cost ? row.cost : row.seconds;
        if(!std::isnan(value)){
            grouped_rows[row.implementation].push_back(&row);
            colors[row.implementation] = row.color;
        }
    }

    double legend_y = origin_y + 40;    // 40 pixels down from top of graph
    for(const auto& entry : grouped_rows){
        auto points = entry.second;
        std::sort(points.begin(), points.end(), [](const BenchmarkRow* lhs, const BenchmarkRow* rhs){
            return lhs->p < rhs->p;
        });

        std::ostringstream polyline;
        bool first = true;
        for(const BenchmarkRow* row : points){
            const double value = use_speedup ? row->speedup : use_cost ? row->cost : row->seconds;
            const double x = scale_x(row->p, min_p, max_p, left, plot_width);
            const double y = scale_y(value, 0.0, max_y, top, plot_height);
            if(!first) polyline << ' ';

            polyline << x << ',' << y;
            first = false;
        }

        out << "<polyline fill=\"none\" stroke=\"" << colors[entry.first]
            << "\" stroke-width=\"2.5\" points=\"" << polyline.str() << "\"/>\n";

        for(const BenchmarkRow* row : points){
            const double value = use_speedup ? row->speedup : use_cost ? row->cost : row->seconds;
            const double x = scale_x(row->p, min_p, max_p, left, plot_width);
            const double y = scale_y(value, 0.0, max_y, top, plot_height);
            out << "<circle cx=\"" << x << "\" cy=\"" << y << "\" r=\"4\" fill=\"" << colors[entry.first] << "\"/>\n";
        }


        double legend_x = origin_x + width - 60;
        double legend_symbol_w = 50.0;
        double legend_label_w = 10.0;
        out << "<line x1=\"" << legend_x << "\" y1=\"" << legend_y
            << "\" x2=\"" << legend_x + legend_symbol_w << "\" y2=\"" << legend_y
            << "\" stroke=\"" << colors[entry.first] << "\" stroke-width=\"3\"/>\n";
        out << "<text x=\"" << legend_x + legend_symbol_w + legend_label_w << "\" y=\"" << (legend_y + 4.0)
            << "\" font-size=\"11\" font-family=\"sans-serif\">" << entry.first << "</text>\n";
        legend_y += 18.0;
    }

    out << "</g>\n";
}

void write_svg(const std::string& path, const std::vector<BenchmarkRow>& rows, const Config& config){
    std::ofstream out(path);
    if(!out){
        throw std::runtime_error("failed to open SVG output: " + path);
    }

    double h_spacing = 360;
    double graph_count = 3;
    double right_magin = 160;
    const double width = 1600.0;
    const double height = 140 + h_spacing * (graph_count);
    out << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << width
        << "\" height=\"" << height << "\" viewBox=\"0 0 " << width << ' ' << height << "\">\n";
    out << "<rect width=\"100%\" height=\"100%\" fill=\"#f8fafc\"/>\n";
    out << "<text x=\""<< width/2 << "\" y=\"36\" text-anchor=\"middle\" font-size=\"24\" font-family=\"sans-serif\">"
        << "Matrix Multiplication Benchmark Summary</text>\n";
    out << "<text x=\""<< width/2 << "\" y=\"60\" text-anchor=\"middle\" font-size=\"13\" font-family=\"sans-serif\" fill=\"#475569\">"
        << "Dimensions: m=" << config.m << ", n=" << config.n << ", q=" << config.q << "</text>\n";


    write_plot_panel(out, rows, config.p_values, "Runtime by P", false, false, 20.0, 90.0, width - right_magin, 320.0);
    write_plot_panel(out, rows, config.p_values, "Speedup vs P=1", true, false, 20.0, 90.0 + h_spacing, width - right_magin, 320.0);
    write_plot_panel(out, rows, config.p_values, "Cost vs Serial", false, true, 20.0, 90.0 + h_spacing * 2, width - right_magin, 320.0);

    out << "</svg>\n";
}

void print_table(const std::vector<BenchmarkRow>& rows){
    std::cout << '\n';
    std::cout << std::left
              << std::setw(28) << "Implementation"
              << std::setw(6) << "P"
              << std::setw(14) << "Seconds"
              << std::setw(14) << "Speedup"
              << std::setw(14) << "VsSerial"
              << std::setw(14) << "Cost"
              << "Status\n";
    std::cout << std::string(100, '-') << '\n';

    for(const BenchmarkRow& row : rows){
        std::cout << std::left
                  << std::setw(28) << row.implementation
                  << std::setw(6) << row.p
                  << std::setw(14) << format_metric(row.seconds)
                  << std::setw(14) << format_metric(row.speedup)
                  << std::setw(14) << format_metric(row.serial_speedup)
                  << std::setw(14) << format_metric(row.cost)
                  << row.status << '\n';
    }
}

std::string build_command(const ImplementationInfo& implementation, int m, int n, int q, int p){
    std::string command;
    if(implementation.launch_with_mpi){
        command += "mpirun -np " + std::to_string(p) + " ";
    }

    command += implementation.command_path + " " +
        std::to_string(m) + " " +
        std::to_string(n) + " " +
        std::to_string(q);

    return command;
}

BenchmarkRow make_benchmark_row(
    const ImplementationInfo& implementation,
    const CommandResult& result,
    int m,
    int n,
    int q,
    int p,
    double serial_seconds,
    bool serial_ok,
    double impl_p1_seconds,
    bool impl_p1_ok
){
    BenchmarkRow row;
    row.implementation = implementation.implementation_name;
    row.color = implementation.color;
    row.m = m;
    row.n = n;
    row.q = q;
    row.p = p;
    row.seconds = result.seconds;
    row.exit_code = result.exit_code;
    row.status = (result.exit_code == 0 && !std::isnan(result.seconds)) ? "ok" : "failed";
    row.command = result.command;
    row.raw_output = trim(result.raw_output);

    const bool row_ok = row.status == "ok";
    if(implementation.is_serial){
        row.speedup = row_ok ? 1.0 : std::numeric_limits<double>::quiet_NaN();
        row.serial_speedup = row_ok ? 1.0 : std::numeric_limits<double>::quiet_NaN();
        row.cost = result.seconds;
        return row;
    }

    row.speedup = (row_ok && impl_p1_ok && result.seconds > 0.0)
        ? impl_p1_seconds / result.seconds
        : std::numeric_limits<double>::quiet_NaN();
    row.serial_speedup = (row_ok && serial_ok && result.seconds > 0.0)
        ? serial_seconds / result.seconds
        : std::numeric_limits<double>::quiet_NaN();
    row.cost = row_ok ? p * result.seconds : std::numeric_limits<double>::quiet_NaN();
    return row;
}

CommandResult run_implementation(const ImplementationInfo& implementation, int m, int n, int q, int p){
    const std::string command = build_command(implementation, m, n, q, p);
    return run_command(command);
}

}

int main(int argc, char* argv[]){
    try {
        const int trials = 5;
        const Config config = parse_args(argc, argv);

        int M = config.m;
        int N = config.n;
        int Q = config.q;
        std::vector<int> P = config.p_values;

        const std::vector<ImplementationInfo> implementations {
            {"Implementation 1", "Implementation 1 (Serial)", "#1d4ed8", "./bin/mm_serial", false, true},
            {"Implementation 2", "Implementation 2 (MM-1D)", "#ea580c", "./bin/mm_1d", true, false},
            {"Implementation 3", "Implementation 3 (MM-2D)", "#059669", "./bin/mm_2d", true, false},
        };

        CommandResult serial_peak;
        for(int test = 0; test < trials; ++test){
            CommandResult res = run_implementation(implementations[0], M, N, Q, 1);
            if(test == 0 || res.seconds < serial_peak.seconds){
                serial_peak = res;
            }
        }
        const CommandResult serial_result = serial_peak;
        const bool serial_ok = serial_result.exit_code == 0 && !std::isnan(serial_result.seconds);

        std::vector<CommandResult> p1_results(implementations.size());
        std::vector<bool> p1_ok(implementations.size(), false);
        p1_results[0] = serial_result;
        p1_ok[0] = serial_ok;

        for(std::size_t i = 1; i < implementations.size(); ++i){
            CommandResult peak;
            for(int test = 0; test < trials; ++test){
                CommandResult res = run_implementation(implementations[i], M, N, Q, 1);
                if(test == 0 || res.seconds < peak.seconds){
                    peak = res;
                }
            }
            p1_results[i] = peak;
            p1_ok[i] = peak.exit_code == 0 && !std::isnan(peak.seconds);
        }

        std::vector<BenchmarkRow> rows;

        for(int p : P){
            std::cout << "Running P= " << p << "..." << std::flush;
            rows.push_back(make_benchmark_row(
                implementations[0],
                serial_result,
                M,
                N,
                Q,
                p,
                serial_result.seconds,
                serial_ok,
                serial_result.seconds,
                serial_ok
            ));

            for(std::size_t i = 1; i < implementations.size(); ++i){
                CommandResult result = p1_results[i];
                if(p != 1){
                    CommandResult peak;
                    for(int test = 0; test < trials; ++test){
                        CommandResult res = run_implementation(implementations[i], M, N, Q, p);
                        if(test == 0 || res.seconds < peak.seconds){
                            peak = res;
                        }
                    }
                    result = peak;
                }
                rows.push_back(make_benchmark_row(
                    implementations[i],
                    result,
                    M,
                    N,
                    Q,
                    p,
                    serial_result.seconds,
                    serial_ok,
                    p1_results[i].seconds,
                    p1_ok[i]
                ));
            }
            std::cout << " done\n" << std::flush;
        }

        print_table(rows);

        if(config.write_csv){
            write_csv(config.csv_path, rows);
            std::cout << "\nCSV written to: " << config.csv_path << '\n';
        }

        if(config.write_svg){
            write_svg(config.svg_path, rows, config);
            std::cout << "SVG graph written to: " << config.svg_path << '\n';
        }

        return 0;
    } catch (const std::exception& error){
        std::cerr << error.what() << '\n';
        print_usage(argv[0]);
        return 1;
    }
}
