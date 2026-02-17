class Devtrace < Formula
  include Language::Python::Virtualenv

  desc "Command-level telemetry capture and scoring for engineering workflows"
  homepage "https://github.com/gupta799/dev-trace"
  url "https://github.com/gupta799/dev-trace/archive/refs/tags/v0.2.0.tar.gz"
  sha256 "2b5e2352cb8a8cc401835cb97f11f944b6ffdbfd2d538894a682922102584d4b"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/devtrace", "init", "--path", testpath/".devtrace"
  end
end
