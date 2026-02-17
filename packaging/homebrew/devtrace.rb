class Devtrace < Formula
  include Language::Python::Virtualenv

  desc "Command-level telemetry capture for CLI agents"
  homepage "https://github.com/jaiydevgupta/dev-trace"
  url "https://files.pythonhosted.org/packages/source/d/devtrace/devtrace-0.1.0.tar.gz"
  sha256 "REPLACE_WITH_SDIST_SHA256"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/devtrace", "init", "--path", testpath/".devtrace"
  end
end
