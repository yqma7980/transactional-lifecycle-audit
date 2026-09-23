#include <Concrete01.h>

#include <cmath>
#include <iomanip>
#include <iostream>

int main() {
  Concrete01 material(1, -30.0, -0.002, -20.0, -0.006);

  material.setTrialStrain(-0.0015);
  material.commitState();
  const double committed_stress = material.getStress();

  material.setTrialStrain(-0.0040);
  const double trial_stress = material.getStress();
  material.revertToLastCommit();
  const double restored_stress = material.getStress();

  const bool restored = std::isfinite(restored_stress) &&
                        restored_stress == committed_stress &&
                        trial_stress != committed_stress;

  std::cout << std::setprecision(17)
            << "committed_stress=" << committed_stress << '\n'
            << "trial_stress=" << trial_stress << '\n'
            << "restored_stress=" << restored_stress << '\n'
            << "native_revert_bitwise_equal=" << (restored ? 1 : 0) << '\n';

  return restored ? 0 : 2;
}
