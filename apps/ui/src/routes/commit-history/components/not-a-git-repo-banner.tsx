/**
 * NotAGitRepoBanner — F22 §IC Section E.
 * Renders only when ``show=true`` (parent observes useCommits().error.status===502
 * with code='not_a_git_repo'). role='alert' so AT users are notified.
 */
import * as React from "react";

export interface NotAGitRepoBannerProps {
  show: boolean;
}

export function NotAGitRepoBanner(
  props: NotAGitRepoBannerProps,
): React.ReactElement | null {
  if (!props.show) return null;
  return (
    <div data-testid="not-a-git-repo-banner" role="alert">
      非 git 目录，git 命令不可用 (not a git repo)
    </div>
  );
}
