import { House } from "lucide-react";
import { useGetHouse } from "@/api/generated/house/house";
import { ExampleDataNotice } from "@/components/house/ExampleDataNotice";
import { LoansSection } from "@/components/house/LoansSection";
import { PutInSection } from "@/components/house/PutInSection";
import { RecentActivitySection } from "@/components/house/RecentActivitySection";
import { SetAsideSection } from "@/components/house/SetAsideSection";
import { SharesSection } from "@/components/house/SharesSection";
import { UpcomingSection } from "@/components/house/UpcomingSection";
import { PageHeader } from "@/components/PageHeader";
import { PageError, PageLoading } from "@/components/PageStates";
import { PAGE_PADDING } from "@/lib/layout";
import { usePersonMaps } from "@/lib/persons";

export function HousePage() {
  const {
    data: res,
    isLoading,
    error,
    refetch,
  } = useGetHouse({ query: { staleTime: 60_000 } });
  const data = res?.status === 200 ? res.data : undefined;
  const { getPersonName, getPersonColor, getPersonIndex } = usePersonMaps(
    data?.persons,
  );

  return (
    <div className={`mx-auto max-w-5xl ${PAGE_PADDING}`}>
      <PageHeader icon={<House className="size-6" />} title="House" />
      {isLoading && <PageLoading label="Loading the house..." />}
      {!isLoading && !data && (
        <PageError error={error} onRetry={() => refetch()} />
      )}
      {data && (
        <div className="space-y-6">
          {data.is_example && <ExampleDataNotice />}
          <PutInSection putIn={data.put_in} owners={data.persons} />
          <SharesSection
            shares={data.shares}
            owners={data.persons}
            getPersonColor={getPersonColor}
            getPersonIndex={getPersonIndex}
          />
          <LoansSection
            loans={data.loans}
            owners={data.persons}
            getPersonColor={getPersonColor}
          />
          <UpcomingSection upcoming={data.upcoming} />
          <SetAsideSection setAside={data.set_aside} />
          <RecentActivitySection
            activity={data.recent_activity}
            owners={data.persons}
            getPersonName={getPersonName}
            getPersonColor={getPersonColor}
          />
        </div>
      )}
    </div>
  );
}
