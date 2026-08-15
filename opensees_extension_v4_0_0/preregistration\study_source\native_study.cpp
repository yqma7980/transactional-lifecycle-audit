#include <Concrete01.h>

#include <cmath>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {

struct CaseSpec {
    std::string case_id;
    std::string mode;
    std::string expected_verdict;
    std::string fault_family;
    std::string injected_candidate;
    double rejected_strain;
    double reference_target;
    double test_target;
    bool comparison_eligible;
    bool observation_coverage;
};

std::string bits_hex(double value) {
    std::uint64_t bits = 0;
    static_assert(sizeof(bits) == sizeof(value), "unexpected double width");
    std::memcpy(&bits, &value, sizeof(value));
    std::ostringstream out;
    out << "0x" << std::hex << std::setw(16) << std::setfill('0') << bits;
    return out.str();
}

const std::map<std::string, CaseSpec> kCases = {
    {"OS-B01", {"OS-B01", "DIRECT_CONTROL", "PASS_INVARIANT", "BENIGN", "NONE",
                 -0.0040, -0.0020, -0.0020, true, true}},
    {"OS-B02", {"OS-B02", "NATIVE_REVERT_CONTROL", "PASS_INVARIANT", "BENIGN", "NONE",
                 -0.0040, -0.0020, -0.0020, true, true}},
    {"OS-F01", {"OS-F01", "PREMATURE_COMMIT_A", "DETECT_LIFECYCLE_DRIFT", "PREMATURE_COMMIT",
                 "C01_PREMATURE_COMMIT", -0.0040, -0.0020, -0.0020, true, true}},
    {"OS-F02", {"OS-F02", "PREMATURE_COMMIT_B", "DETECT_LIFECYCLE_DRIFT", "PREMATURE_COMMIT",
                 "C01_PREMATURE_COMMIT", -0.0030, -0.0010, -0.0010, true, true}},
    {"OS-F03", {"OS-F03", "ROLLBACK_OMISSION", "DETECT_LIFECYCLE_DRIFT", "ROLLBACK_OMISSION",
                 "C02_ROLLBACK_DISPATCH", -0.0040, -0.0020, -0.0020, true, true}},
    {"OS-F04", {"OS-F04", "PERSISTENT_HISTORY_ESCAPE", "DETECT_LIFECYCLE_DRIFT",
                 "PERSISTENT_HISTORY_ESCAPE", "C03_EXTERNAL_STATE_OWNER", -0.0040,
                 -0.0020, -0.0020, true, true}},
    {"OS-I01", {"OS-I01", "DIFFERENT_REPLAY_TARGET", "INVALID_COMPARISON", "INVALID_CONTROL",
                 "NONE", -0.0040, -0.0020, -0.0021, false, true}},
    {"OS-U01", {"OS-U01", "MASKED_OBSERVATION", "UNSUPPORTED_OBSERVATION", "UNSUPPORTED_CONTROL",
                 "NONE", -0.0040, -0.0020, -0.0020, true, false}},
};

void initialize_committed(Concrete01& material) {
    material.revertToStart();
    material.setTrialStrain(-0.0015);
    material.commitState();
    material.revertToLastCommit();
}

void write_bool(const char* key, bool value, bool comma = true) {
    std::cout << "\"" << key << "\":" << (value ? "true" : "false");
    if (comma) std::cout << ',';
}

void write_number(const char* key, double value, bool comma = true) {
    std::cout << "\"" << key << "\":" << std::setprecision(17) << value;
    if (comma) std::cout << ',';
}

void write_string(const char* key, const std::string& value, bool comma = true) {
    std::cout << "\"" << key << "\":\"" << value << "\"";
    if (comma) std::cout << ',';
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "usage: opensees_native_study CASE_ID RUN_ID\n";
        return 2;
    }

    const std::string case_id = argv[1];
    const std::string run_id = argv[2];
    const auto found = kCases.find(case_id);
    if (found == kCases.end()) {
        std::cerr << "unknown case: " << case_id << '\n';
        return 3;
    }
    const CaseSpec& spec = found->second;

    Concrete01 reference(1001, -30.0, -0.0020, -20.0, -0.0060);
    Concrete01 test(1002, -30.0, -0.0020, -20.0, -0.0060);
    initialize_committed(reference);
    initialize_committed(test);

    const double initial_energy = test.getEnergy();
    reference.setTrialStrain(spec.reference_target);
    const double reference_stress = reference.getStress();
    const double reference_tangent = reference.getTangent();

    bool commit_violation = false;
    bool rollback_omission = false;
    bool ownership_violation = false;
    bool output_provenance_violation = false;
    bool operator_version_incompatibility = false;
    bool native_revert_called = false;
    bool rejected_trial_exercised = false;
    double escaped_cache = 0.0;
    double rejected_stress = 0.0;
    double rejected_tangent = 0.0;

    if (spec.mode != "DIRECT_CONTROL") {
        test.setTrialStrain(spec.rejected_strain);
        rejected_trial_exercised = true;
        rejected_stress = test.getStress();
        rejected_tangent = test.getTangent();
    }

    if (spec.mode == "PREMATURE_COMMIT_A" || spec.mode == "PREMATURE_COMMIT_B") {
        test.commitState();
        commit_violation = true;
        test.revertToLastCommit();
        native_revert_called = true;
    } else if (spec.mode == "ROLLBACK_OMISSION") {
        rollback_omission = true;
    } else if (spec.mode == "PERSISTENT_HISTORY_ESCAPE") {
        escaped_cache = rejected_stress * 1.0e-6;
        ownership_violation = true;
        output_provenance_violation = true;
        test.revertToLastCommit();
        native_revert_called = true;
    } else if (spec.mode != "DIRECT_CONTROL") {
        test.revertToLastCommit();
        native_revert_called = true;
    }

    const double energy_before_replay = test.getEnergy();
    test.setTrialStrain(spec.test_target);
    const double physical_stress = test.getStress();
    const double physical_tangent = test.getTangent();
    const double reported_stress = physical_stress + escaped_cache;
    const double reported_tangent = physical_tangent;

    std::cout << '{';
    write_string("case_id", spec.case_id);
    write_string("run_id", run_id);
    write_string("mode", spec.mode);
    write_string("expected_verdict", spec.expected_verdict);
    write_string("fault_family", spec.fault_family);
    write_string("injected_candidate", spec.injected_candidate);
    write_string("native_host", "OpenSees");
    write_string("native_host_version", "3.8.0");
    write_string("lifecycle_tier", "TIER_A_NATIVE_MATERIAL_API");
    write_bool("comparison_eligible", spec.comparison_eligible);
    write_bool("observation_coverage", spec.observation_coverage);
    write_bool("rejected_trial_exercised", rejected_trial_exercised);
    write_bool("native_revert_called", native_revert_called);
    write_bool("commit_violation", commit_violation);
    write_bool("rollback_omission", rollback_omission);
    write_bool("ownership_violation", ownership_violation);
    write_bool("output_provenance_violation", output_provenance_violation);
    write_bool("operator_version_incompatibility", operator_version_incompatibility);
    write_number("initial_energy", initial_energy);
    write_number("energy_before_replay", energy_before_replay);
    write_number("rejected_strain", spec.rejected_strain);
    write_number("rejected_stress", rejected_stress);
    write_number("rejected_tangent", rejected_tangent);
    write_number("reference_target", spec.reference_target);
    write_number("test_target", spec.test_target);
    write_number("reference_stress", reference_stress);
    write_number("reference_tangent", reference_tangent);
    write_number("physical_stress", physical_stress);
    write_number("physical_tangent", physical_tangent);
    write_number("escaped_cache", escaped_cache);
    write_number("reported_stress", reported_stress);
    write_number("reported_tangent", reported_tangent);
    write_string("reference_stress_bits", bits_hex(reference_stress));
    write_string("reference_tangent_bits", bits_hex(reference_tangent));
    write_string("reported_stress_bits", bits_hex(reported_stress));
    write_string("reported_tangent_bits", bits_hex(reported_tangent));
    write_bool("response_bitwise_equal",
               bits_hex(reference_stress) == bits_hex(reported_stress) &&
               bits_hex(reference_tangent) == bits_hex(reported_tangent), false);
    std::cout << "}\n";
    return 0;
}
